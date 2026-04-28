from datetime import date, timedelta
from typing import Annotated, Any
import asyncio
import json

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import require_admin
from app.core.config import get_settings

router = APIRouter(prefix="/admin/reports", tags=["admin-reports"])


async def _admin_get(client: httpx.AsyncClient, settings, path: str, params: dict | None = None) -> Any:
    try:
        response = await client.get(
            f"{settings.sub2api_base_url.rstrip('/')}/{path.lstrip('/')}",
            headers={"x-api-key": settings.sub2api_admin_api_key},
            params=params,
        )
        response.raise_for_status()
        return response.json().get("data")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


async def _admin_get_simple(path: str, params: dict | None = None) -> Any:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{settings.sub2api_base_url.rstrip('/')}/{path.lstrip('/')}",
                headers={"x-api-key": settings.sub2api_admin_api_key},
                params=params,
            )
        response.raise_for_status()
        return response.json().get("data")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


async def _admin_get_raw(path: str, params: dict | None = None) -> Any:
    """返回原始 JSON（不提取 .data），适用于直接返回数组的接口。"""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{settings.sub2api_base_url.rstrip('/')}/{path.lstrip('/')}",
                headers={"x-api-key": settings.sub2api_admin_api_key},
                params=params,
            )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


def _days(start: date, end: date) -> int:
    return max(1, (end - start).days + 1)


def _parse_dates(start_date: str | None, end_date: str | None) -> tuple[date, date]:
    end = date.fromisoformat(end_date) if end_date else date.today()
    start = date.fromisoformat(start_date) if start_date else end - timedelta(days=29)
    if start > end:
        start, end = end, start
    return start, end


@router.get("/overview")
async def get_overview(
    _: Annotated[dict, Depends(require_admin)],
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    start, end = _parse_dates(start_date, end_date)
    days = _days(start, end)
    settings = get_settings()
    data = await _admin_get_simple("/admin/dashboard/stats")

    try:
        conn = await asyncpg.connect(settings.database_url)
        try:
            row = await conn.fetchrow(
                """SELECT COUNT(DISTINCT user_id) AS cnt FROM usage_logs
                   WHERE created_at >= $1::date AND created_at < $2::date + interval '1 day'""",
                start, end,
            )
            data["period_active_users"] = row["cnt"]
            data["period_days"] = days
        finally:
            await conn.close()
    except Exception:
        data["period_active_users"] = None
        data["period_days"] = days

    return data


@router.get("/trend")
async def get_trend(
    _: Annotated[dict, Depends(require_admin)],
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    timezone: str = Query("Asia/Shanghai"),
):
    start, end = _parse_dates(start_date, end_date)
    settings = get_settings()
    sql = """
        SELECT
            (created_at AT TIME ZONE $3)::date AS day,
            COALESCE(SUM(input_tokens), 0)           AS input_tokens,
            COALESCE(SUM(output_tokens), 0)          AS output_tokens,
            COALESCE(SUM(cache_creation_tokens), 0)  AS cache_creation_tokens,
            COALESCE(SUM(cache_read_tokens), 0)      AS cache_read_tokens,
            COUNT(*)                                 AS requests,
            ROUND(SUM(total_cost * COALESCE(account_rate_multiplier, 1.0))::numeric, 4) AS actual_cost
        FROM usage_logs
        WHERE created_at >= $1::date AT TIME ZONE $3
          AND created_at < ($2::date + interval '1 day') AT TIME ZONE $3
        GROUP BY day
        ORDER BY day
    """
    try:
        conn = await asyncpg.connect(settings.database_url)
        try:
            rows = await conn.fetch(sql, start, end, timezone)
        finally:
            await conn.close()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    trend = [
        {
            "date": str(row["day"]),
            "input_tokens": row["input_tokens"],
            "output_tokens": row["output_tokens"],
            "cache_creation_tokens": row["cache_creation_tokens"],
            "cache_read_tokens": row["cache_read_tokens"],
            "requests": row["requests"],
            "actual_cost": float(row["actual_cost"]),
        }
        for row in rows
    ]
    return {"trend": trend, "start_date": str(start), "end_date": str(end), "granularity": "day"}


@router.get("/models")
async def get_models(
    _: Annotated[dict, Depends(require_admin)],
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    timezone: str = Query("Asia/Shanghai"),
):
    start, end = _parse_dates(start_date, end_date)
    data = await _admin_get_simple("/admin/dashboard/models", {
        "start_date": str(start), "end_date": str(end), "timezone": timezone,
    })
    return data


@router.get("/accounts")
async def get_accounts(
    _: Annotated[dict, Depends(require_admin)],
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    start, end = _parse_dates(start_date, end_date)
    settings = get_settings()
    sql = """
        WITH stats AS (
            SELECT
                a.id,
                COALESCE(a.name, '未知账号-' || ul.account_id::text)  AS name,
                COALESCE(a.platform, '')                              AS platform,
                COALESCE(a.status, 'deleted')                         AS status,
                a.last_used_at,
                a.expires_at,
                COALESCE(REGEXP_REPLACE(a.name, '[-_].*$', ''), '已删除') AS grp,
                COUNT(ul.id)                                           AS requests,
                COALESCE(SUM(ul.total_cost * COALESCE(ul.account_rate_multiplier, 1.0)), 0) AS total_cost,
                COALESCE(SUM(ul.input_tokens), 0)              AS input_tokens,
                COALESCE(SUM(ul.output_tokens), 0)             AS output_tokens,
                COALESCE(SUM(ul.cache_creation_tokens), 0)     AS cache_creation_tokens,
                COALESCE(SUM(ul.cache_read_tokens), 0)         AS cache_read_tokens
            FROM usage_logs ul
            LEFT JOIN accounts a ON a.id = ul.account_id
            WHERE ul.created_at >= $1
              AND ul.created_at < $2::date + interval '1 day'
            GROUP BY a.id, a.name, a.platform, a.status, a.last_used_at, a.expires_at, ul.account_id
        )
        SELECT
            grp                                  AS group_name,
            COUNT(*)                             AS account_count,
            SUM(requests)                        AS total_requests,
            ROUND(SUM(total_cost)::numeric, 4)   AS total_cost,
            SUM(input_tokens)                    AS input_tokens,
            SUM(output_tokens)                   AS output_tokens,
            SUM(cache_creation_tokens)           AS cache_creation_tokens,
            SUM(cache_read_tokens)               AS cache_read_tokens,
            MAX(last_used_at)                    AS last_used_at,
            JSON_AGG(
                JSON_BUILD_OBJECT(
                    'id',          id,
                    'name',        name,
                    'platform',    platform,
                    'status',      status,
                    'requests',      requests,
                    'total_cost',    ROUND(total_cost::numeric, 4),
                    'input_tokens',            input_tokens,
                    'output_tokens',           output_tokens,
                    'cache_creation_tokens',   cache_creation_tokens,
                    'cache_read_tokens',       cache_read_tokens,
                    'last_used_at',  last_used_at,
                    'expires_at',    expires_at
                ) ORDER BY requests DESC
            ) AS accounts
        FROM stats
        GROUP BY grp
        ORDER BY total_requests DESC
    """
    try:
        conn = await asyncpg.connect(settings.database_url)
        try:
            rows = await conn.fetch(sql, start, end)
        finally:
            await conn.close()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    result = []
    for row in rows:
        accounts_raw = row["accounts"]
        accounts = json.loads(accounts_raw) if isinstance(accounts_raw, str) else accounts_raw
        result.append({
            "group_name": row["group_name"],
            "account_count": row["account_count"],
            "total_requests": row["total_requests"],
            "total_cost": float(row["total_cost"]),
            "input_tokens": row["input_tokens"],
            "output_tokens": row["output_tokens"],
            "cache_creation_tokens": row["cache_creation_tokens"],
            "cache_read_tokens": row["cache_read_tokens"],
            "last_used_at": row["last_used_at"].isoformat() if row["last_used_at"] else None,
            "accounts": accounts,
        })
    return result


@router.get("/account-latency")
async def get_account_latency(
    _: Annotated[dict, Depends(require_admin)],
    limit: int = Query(300, ge=1, le=1000),
    recent_minutes: int = Query(10, ge=1, le=60),
):
    """按账号统计最近 N 条请求的 TTFT / 总时延，以及最近 M 分钟的实时数据，支持按模型细分。"""
    settings = get_settings()

    sql_all = """
        WITH ranked AS (
            SELECT
                ul.account_id,
                a.name                                                  AS account_name,
                COALESCE(REGEXP_REPLACE(a.name, '[-_].*$', ''), '未知') AS grp,
                ul.model,
                ul.first_token_ms,
                ul.duration_ms,
                ROW_NUMBER() OVER (PARTITION BY ul.account_id ORDER BY ul.created_at DESC) AS rn
            FROM usage_logs ul
            INNER JOIN accounts a ON a.id = ul.account_id AND a.status != 'deleted'
            WHERE ul.duration_ms IS NOT NULL AND ul.duration_ms > 0
        ),
        recent AS (
            SELECT
                ul.account_id,
                ul.model,
                ul.first_token_ms,
                ul.duration_ms
            FROM usage_logs ul
            WHERE ul.created_at >= NOW() - ($2 || ' minutes')::interval
              AND ul.duration_ms IS NOT NULL AND ul.duration_ms > 0
        )
        SELECT
            r.account_id,
            r.account_name,
            r.grp,
            r.model,
            COUNT(*)                                                                         AS requests,
            ROUND(AVG(r.first_token_ms) FILTER (WHERE r.first_token_ms > 0))::int           AS ttft_avg,
            PERCENTILE_CONT(0.9) WITHIN GROUP (
                ORDER BY CASE WHEN r.first_token_ms > 0 THEN r.first_token_ms END
            )::int                                                                           AS ttft_p90,
            ROUND(AVG(r.duration_ms))::int                                                   AS dur_avg,
            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY r.duration_ms)::int                 AS dur_p90,
            COUNT(rc.account_id)                                                             AS recent_requests,
            ROUND(AVG(rc.first_token_ms) FILTER (WHERE rc.first_token_ms > 0))::int         AS recent_ttft_avg,
            PERCENTILE_CONT(0.9) WITHIN GROUP (
                ORDER BY CASE WHEN rc.first_token_ms > 0 THEN rc.first_token_ms END
            )::int                                                                           AS recent_ttft_p90,
            ROUND(AVG(rc.duration_ms))::int                                                  AS recent_dur_avg
        FROM ranked r
        LEFT JOIN recent rc ON rc.account_id = r.account_id AND rc.model = r.model
        WHERE r.rn <= $1
        GROUP BY r.account_id, r.account_name, r.grp, r.model
        ORDER BY COUNT(*) DESC, r.account_id, r.model
    """

    try:
        conn = await asyncpg.connect(settings.database_url)
        try:
            rows = await conn.fetch(sql_all, limit, str(recent_minutes))
        finally:
            await conn.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # 按账号聚合，模型作为子列表
    accounts: dict[int, dict] = {}
    for row in rows:
        aid = row["account_id"]
        if aid not in accounts:
            accounts[aid] = {
                "account_id": aid,
                "account_name": row["account_name"] or f"id={aid}",
                "group": row["grp"],
                "models": [],
            }
        accounts[aid]["models"].append({
            "model": row["model"] or "unknown",
            "requests": row["requests"],
            "ttft_avg": row["ttft_avg"],
            "ttft_p90": row["ttft_p90"],
            "dur_avg": row["dur_avg"],
            "dur_p90": row["dur_p90"],
            "recent_requests": row["recent_requests"],
            "recent_ttft_avg": row["recent_ttft_avg"],
            "recent_ttft_p90": row["recent_ttft_p90"],
            "recent_dur_avg": row["recent_dur_avg"],
        })

    # 按组聚合，组内账号已按请求数降序（SQL 保证），组本身也按总请求数降序
    groups: dict[str, dict] = {}
    for acct in accounts.values():
        g = acct["group"]
        if g not in groups:
            groups[g] = {"group": g, "accounts": [], "total_requests": 0}
        groups[g]["accounts"].append(acct)
        groups[g]["total_requests"] += sum(m["requests"] for m in acct["models"])

    sorted_groups = sorted(groups.values(), key=lambda x: x["total_requests"], reverse=True)
    for grp in sorted_groups:
        del grp["total_requests"]

    return {"groups": sorted_groups, "limit": limit, "recent_minutes": recent_minutes}


@router.get("/users")
async def search_users(
    _: Annotated[dict, Depends(require_admin)],
    search: str = Query(""),
    page_size: int = Query(20, ge=1, le=100),
):
    data = await _admin_get_simple(
        "/admin/users",
        {"search": search, "page": 1, "page_size": page_size},
    )
    items = data.get("items", []) if data else []
    return [
        {"id": u["id"], "email": u["email"], "username": u.get("username", "")}
        for u in items
    ]


@router.get("/users/{user_id}/daily-trend")
async def get_user_daily_trend(
    user_id: int,
    _: Annotated[dict, Depends(require_admin)],
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    timezone: str = Query("Asia/Shanghai"),
):
    start, end = _parse_dates(start_date, end_date)
    # 最多查 60 天，避免请求过多
    if (end - start).days > 59:
        start = end - timedelta(days=59)

    days = [(start + timedelta(days=i)) for i in range((end - start).days + 1)]
    settings = get_settings()

    async def fetch_day(client: httpx.AsyncClient, d: date) -> dict:
        ds = str(d)
        try:
            resp = await client.get(
                f"{settings.sub2api_base_url.rstrip('/')}/admin/dashboard/user-breakdown",
                headers={"x-api-key": settings.sub2api_admin_api_key},
                params={"start_date": ds, "end_date": ds, "timezone": timezone},
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            users = data.get("users", [])
            user_data = next((u for u in users if u["user_id"] == user_id), None)
            if user_data:
                return {
                    "date": ds,
                    "actual_cost": user_data["actual_cost"],
                    "account_cost": user_data.get("account_cost", 0.0),
                    "requests": user_data["requests"],
                    "total_tokens": user_data["total_tokens"],
                }
        except Exception:
            pass
        return {"date": ds, "actual_cost": 0.0, "account_cost": 0.0, "requests": 0, "total_tokens": 0}

    async with httpx.AsyncClient(timeout=20) as client:
        results = await asyncio.gather(*[fetch_day(client, d) for d in days])

    return {"items": list(results)}


@router.get("/user-breakdown")
async def get_user_breakdown(
    _: Annotated[dict, Depends(require_admin)],
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    timezone: str = Query("Asia/Shanghai"),
):
    start, end = _parse_dates(start_date, end_date)
    data = await _admin_get_simple(
        "/admin/dashboard/user-breakdown",
        {"start_date": str(start), "end_date": str(end), "timezone": timezone},
    )
    return data


@router.get("/accounts-list")
async def get_accounts_list(
    _: Annotated[dict, Depends(require_admin)],
    page_size: int = Query(200, ge=1, le=200),
):
    data = await _admin_get_simple("/admin/accounts", {"page": 1, "page_size": page_size})
    items = data.get("items", []) if data else []
    return [
        {
            "id": a["id"],
            "name": a["name"],
            "priority": a.get("priority", 0),
            "status": a.get("status", ""),
            "platform": a.get("platform", ""),
            "groups": [{"id": g["id"], "name": g["name"]} for g in (a.get("groups") or [])],
            "schedulable": a.get("schedulable", False),
            "temp_unschedulable_until": a.get("temp_unschedulable_until"),
            "temp_unschedulable_reason": a.get("temp_unschedulable_reason", ""),
            "rate_limited_at": a.get("rate_limited_at"),
            "rate_limit_reset_at": a.get("rate_limit_reset_at"),
            "overload_until": a.get("overload_until"),
        }
        for a in items
    ]


@router.get("/accounts/{account_id}/scheduled-test-plans")
async def get_account_scheduled_plans(
    account_id: int,
    _: Annotated[dict, Depends(require_admin)],
):
    return await _admin_get_raw(f"/admin/accounts/{account_id}/scheduled-test-plans")


@router.get("/scheduled-test-plans/{plan_id}/results")
async def get_plan_results(
    plan_id: int,
    _: Annotated[dict, Depends(require_admin)],
    limit: int = Query(48, ge=1, le=300),
    timezone: str = Query("Asia/Shanghai"),
):
    return await _admin_get_raw(
        f"/admin/scheduled-test-plans/{plan_id}/results",
        {"limit": limit, "timezone": timezone},
    )


@router.get("/users/{user_id}/usage-logs")
async def get_user_usage_logs(
    user_id: int,
    _: Annotated[dict, Depends(require_admin)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    params: dict[str, Any] = {"user_id": user_id, "page": page, "per_page": per_page}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    data = await _admin_get_simple("/admin/usage", params)
    return data

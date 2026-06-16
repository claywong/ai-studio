"""把 request_logs 按小时导出为 JSONL+gzip 并上传腾讯云 COS，校验成功后安全删库。

设计要点：
- 时间一律按 UTC 整点对齐（created_at 是 timestamptz）。
- 每个小时区间 [H, H+1) 导出为一个或多个 .jsonl.gz 分片，上传到
  {prefix}/YYYY/MM/DD/HH/part-NNNN.jsonl.gz。
- 水位表 request_logs_archive_runs 记录每个小时的状态（pending/uploaded/deleted），
  保证幂等、可重跑、可审计；删除前强制校验该小时已 uploaded 且超过保留期。
- 不修改 sub2api 本体，纯 asyncpg + cos-python-sdk-v5。
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import asyncpg

logger = logging.getLogger(__name__)

WATERMARK_DDL = """
CREATE TABLE IF NOT EXISTS request_logs_archive_runs (
    hour_start   timestamptz PRIMARY KEY,
    status       text        NOT NULL DEFAULT 'pending',
    row_count    bigint      NOT NULL DEFAULT 0,
    byte_count   bigint      NOT NULL DEFAULT 0,
    object_keys  jsonb       NOT NULL DEFAULT '[]'::jsonb,
    error        text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
"""


def aligned_hour(dt: datetime) -> datetime:
    """把任意时刻向下取整到 UTC 整点。"""
    dt = dt.astimezone(UTC)
    return dt.replace(minute=0, second=0, microsecond=0)


def iter_hours(start: datetime, end: datetime) -> Iterator[datetime]:
    """产出 [start, end) 之间每个 UTC 整点的起始时刻（含 start，不含 end）。"""
    cur = aligned_hour(start)
    end = aligned_hour(end)
    while cur < end:
        yield cur
        cur += timedelta(hours=1)


def _object_key(prefix: str, hour_start: datetime, part: int) -> str:
    h = hour_start.astimezone(UTC)
    return (
        f"{prefix.strip('/')}/{h:%Y/%m/%d/%H}/part-{part:04d}.jsonl.gz"
    )


def _hour_prefix(prefix: str, hour_start: datetime) -> str:
    """某小时目录的 COS 前缀，如 request-logs/2026/06/16/08/。"""
    h = hour_start.astimezone(UTC)
    return f"{prefix.strip('/')}/{h:%Y/%m/%d/%H}/"


def _md5_hex(path: str) -> str:
    h = hashlib.md5()  # noqa: S324 — 仅用于与 COS ETag 比对完整性，非安全用途
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class CosUploader:
    """对 cos-python-sdk-v5 的薄封装，便于测试时 mock。"""

    def __init__(
        self,
        secret_id: str,
        secret_key: str,
        region: str,
        bucket: str,
        endpoint: str = "",
    ) -> None:
        from qcloud_cos import CosConfig, CosS3Client

        self.bucket = bucket
        cfg = CosConfig(
            Region=region,
            SecretId=secret_id,
            SecretKey=secret_key,
            Endpoint=endpoint or None,
            Scheme="https",
        )
        self._client = CosS3Client(cfg)

    def put_file(self, local_path: str, key: str) -> str:
        """上传本地文件，返回 COS 返回的 ETag（去掉引号）。"""
        with open(local_path, "rb") as fp:
            resp = self._client.put_object(
                Bucket=self.bucket,
                Body=fp,
                Key=key,
                ContentType="application/gzip",
            )
        return (resp.get("ETag") or "").strip('"')

    def head(self, key: str) -> dict:
        return self._client.head_object(Bucket=self.bucket, Key=key)

    def list_objects(self, prefix: str) -> list[dict]:
        """列出指定前缀下所有对象，自动翻页。

        返回 [{"key": str, "size": int, "last_modified": str}, ...]，按 key 升序。
        """
        out: list[dict] = []
        marker = ""
        while True:
            resp = self._client.list_objects(
                Bucket=self.bucket, Prefix=prefix, Marker=marker, MaxKeys=1000
            )
            for c in resp.get("Contents", []) or []:
                out.append(
                    {
                        "key": c.get("Key", ""),
                        "size": int(c.get("Size", 0)),
                        "last_modified": c.get("LastModified", ""),
                    }
                )
            if resp.get("IsTruncated") == "true":
                marker = resp.get("NextMarker", "")
                if not marker:
                    break
            else:
                break
        out.sort(key=lambda o: o["key"])
        return out

    def delete_object(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key)


@dataclass
class HourResult:
    hour_start: datetime
    row_count: int = 0
    byte_count: int = 0
    object_keys: list[str] = field(default_factory=list)
    deleted_rows: int = 0
    skipped: bool = False
    reason: str = ""


def _row_to_json(row: asyncpg.Record) -> str:
    created = row["created_at"]
    return json.dumps(
        {
            "request_id": row["request_id"],
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "email": row["email"],
            "created_at": created.astimezone(UTC).isoformat()
            if isinstance(created, datetime)
            else created,
            "request_body": row["request_body"],
            "response_body": row["response_body"],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


async def _export_hour_parts(
    conn: asyncpg.Connection,
    hour_start: datetime,
    tmp_dir: str,
    max_rows_per_part: int,
) -> tuple[list[str], int]:
    """流式读取该小时的行，写成若干本地 .jsonl.gz 分片。

    返回 (本地文件路径列表, 总行数)。无数据时返回 ([], 0)。
    """
    hour_end = hour_start + timedelta(hours=1)
    paths: list[str] = []
    total = 0
    part = 1
    rows_in_part = 0
    gz: gzip.GzipFile | None = None

    def _open_part(p: int) -> gzip.GzipFile:
        path = os.path.join(tmp_dir, f"part-{p:04d}.jsonl.gz")
        paths.append(path)
        # mtime=0 让 gzip 输出对相同内容稳定可复现
        return gzip.GzipFile(filename=path, mode="wb", mtime=0)

    # 事务内只读游标，按 created_at 升序流式拉取，避免一次性载入内存
    async with conn.transaction():
        cursor = conn.cursor(
            """SELECT rl.request_id, rl.session_id, rl.user_id,
                      u.email, rl.request_body, rl.response_body, rl.created_at
               FROM request_logs rl
               LEFT JOIN users u ON u.id = rl.user_id
               WHERE rl.created_at >= $1 AND rl.created_at < $2
               ORDER BY rl.created_at""",
            hour_start,
            hour_end,
        )
        async for row in cursor:
            if gz is None:
                gz = _open_part(part)
            line = _row_to_json(row) + "\n"
            gz.write(line.encode("utf-8"))
            total += 1
            rows_in_part += 1
            if rows_in_part >= max_rows_per_part:
                gz.close()
                gz = None
                part += 1
                rows_in_part = 0

    if gz is not None:
        gz.close()

    return paths, total


async def ensure_watermark_table(conn: asyncpg.Connection) -> None:
    await conn.execute(WATERMARK_DDL)


async def _mark(
    conn: asyncpg.Connection,
    hour_start: datetime,
    status: str,
    *,
    row_count: int = 0,
    byte_count: int = 0,
    object_keys: list[str] | None = None,
    error: str | None = None,
) -> None:
    await conn.execute(
        """INSERT INTO request_logs_archive_runs
               (hour_start, status, row_count, byte_count, object_keys, error, updated_at)
           VALUES ($1, $2, $3, $4, $5::jsonb, $6, now())
           ON CONFLICT (hour_start) DO UPDATE SET
               status = EXCLUDED.status,
               row_count = EXCLUDED.row_count,
               byte_count = EXCLUDED.byte_count,
               object_keys = EXCLUDED.object_keys,
               error = EXCLUDED.error,
               updated_at = now()""",
        hour_start,
        status,
        row_count,
        byte_count,
        json.dumps(object_keys or []),
        error,
    )


async def _delete_hour(
    conn: asyncpg.Connection, hour_start: datetime, batch_size: int
) -> int:
    """分批删除某小时区间的行，返回删除总数。

    PG 不支持 DELETE ... LIMIT，用子查询 LIMIT 限定每批，循环到删空为止。
    """
    hour_end = hour_start + timedelta(hours=1)
    deleted = 0
    while True:
        status = await conn.execute(
            """DELETE FROM request_logs
               WHERE request_id IN (
                   SELECT request_id FROM request_logs
                   WHERE created_at >= $1 AND created_at < $2
                   LIMIT $3
               )""",
            hour_start,
            hour_end,
            batch_size,
        )
        # status 形如 "DELETE 5000"
        count = int(status.split()[-1])
        deleted += count
        if count < batch_size:
            break
    return deleted


async def _upload_and_verify(
    uploader: CosUploader,
    local_paths: list[str],
    prefix: str,
    hour_start: datetime,
) -> tuple[list[str], int]:
    """上传每个分片并回读校验（ETag/大小），返回 (object_keys, 总字节数)。

    任一分片校验不一致即抛异常，调用方据此跳过删除。
    """
    keys: list[str] = []
    total_bytes = 0
    for idx, path in enumerate(local_paths, start=1):
        key = _object_key(prefix, hour_start, idx)
        local_size = os.path.getsize(path)
        local_md5 = _md5_hex(path)
        etag = uploader.put_file(path, key)
        head = uploader.head(key)
        remote_size = int(head.get("Content-Length", -1))
        if remote_size != local_size:
            raise RuntimeError(
                f"COS 大小不一致 key={key} local={local_size} remote={remote_size}"
            )
        # COS 非分块上传的 ETag 即对象 MD5；分块上传会带 '-' 后缀，此处单文件上传应一致
        if etag and "-" not in etag and etag != local_md5:
            raise RuntimeError(
                f"COS ETag 不一致 key={key} local_md5={local_md5} etag={etag}"
            )
        keys.append(key)
        total_bytes += local_size
    return keys, total_bytes


def _cleanup_stale_parts(
    uploader: CosUploader, prefix: str, hour_start: datetime, kept_parts: int
) -> list[str]:
    """删除该小时目录下编号 > kept_parts 的残留旧分片。

    应对「重跑时本次片数少于上次」导致的旧对象残留。返回被删除的 key 列表。
    """
    keep = {_object_key(prefix, hour_start, i) for i in range(1, kept_parts + 1)}
    removed: list[str] = []
    for obj in uploader.list_objects(_hour_prefix(prefix, hour_start)):
        key = obj["key"]
        if key not in keep and key.endswith(".jsonl.gz"):
            uploader.delete_object(key)
            removed.append(key)
            logger.info("清理残留旧分片 %s", key)
    return removed


async def archive_hour(
    conn: asyncpg.Connection,
    uploader: CosUploader | None,
    hour_start: datetime,
    *,
    prefix: str,
    max_rows_per_part: int,
    delete_cutoff: datetime,
    delete_batch_size: int,
    dry_run: bool = False,
    allow_delete: bool = True,
) -> HourResult:
    """归档单个小时：导出 → 上传校验 → 记水位 → 满足条件则删库。"""
    result = HourResult(hour_start=hour_start)

    with tempfile.TemporaryDirectory(prefix="reqlog-archive-") as tmp_dir:
        paths, rows = await _export_hour_parts(
            conn, hour_start, tmp_dir, max_rows_per_part
        )
        result.row_count = rows

        if rows == 0:
            # 空小时：标记 deleted（无需保留），不产生对象
            if not dry_run:
                await _mark(conn, hour_start, "deleted", row_count=0)
            result.reason = "no rows"
            return result

        if dry_run or uploader is None:
            result.byte_count = sum(os.path.getsize(p) for p in paths)
            result.object_keys = [
                _object_key(prefix, hour_start, i) for i in range(1, len(paths) + 1)
            ]
            result.reason = "dry-run (未上传/未删除)"
            return result

        keys, total_bytes = await _upload_and_verify(
            uploader, paths, prefix, hour_start
        )
        # 清理重跑残留：删掉该小时目录里编号大于本次片数的旧对象
        _cleanup_stale_parts(uploader, prefix, hour_start, len(keys))
        result.object_keys = keys
        result.byte_count = total_bytes
        await _mark(
            conn,
            hour_start,
            "uploaded",
            row_count=rows,
            byte_count=total_bytes,
            object_keys=keys,
        )

    # 删除条件：已上传 + 整个小时区间早于保留截止点
    hour_end = hour_start + timedelta(hours=1)
    if not allow_delete:
        result.reason = "已上传，按参数跳过删除"
        return result
    if hour_end > delete_cutoff:
        result.reason = f"已上传，未过保留期（cutoff={delete_cutoff:%Y-%m-%d %H:%M}Z）"
        return result

    deleted = await _delete_hour(conn, hour_start, delete_batch_size)
    result.deleted_rows = deleted
    await _mark(
        conn,
        hour_start,
        "deleted",
        row_count=rows,
        byte_count=result.byte_count,
        object_keys=keys,
    )
    result.reason = "已上传并删除"
    return result


async def _already_deleted(conn: asyncpg.Connection, hour_start: datetime) -> bool:
    status = await conn.fetchval(
        "SELECT status FROM request_logs_archive_runs WHERE hour_start = $1",
        hour_start,
    )
    return status == "deleted"


async def summarize_runs(
    database_url: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 200,
) -> list[dict]:
    """读取水位表 request_logs_archive_runs 的状态，按小时倒序返回。

    可选按 [start, end) 过滤；表不存在时返回空列表。
    """
    conn = await asyncpg.connect(database_url)
    try:
        exists = await conn.fetchval("SELECT to_regclass('request_logs_archive_runs')")
        if not exists:
            return []
        where = []
        params: list = []
        if start is not None:
            params.append(start)
            where.append(f"hour_start >= ${len(params)}")
        if end is not None:
            params.append(end)
            where.append(f"hour_start < ${len(params)}")
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        params.append(limit)
        rows = await conn.fetch(
            f"""SELECT hour_start, status, row_count, byte_count,
                       jsonb_array_length(object_keys) AS parts, error, updated_at
                FROM request_logs_archive_runs{clause}
                ORDER BY hour_start DESC
                LIMIT ${len(params)}""",
            *params,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()



async def archive_range(
    database_url: str,
    uploader: CosUploader | None,
    start: datetime,
    end: datetime,
    *,
    prefix: str,
    max_rows_per_part: int,
    retention_hours: int,
    delete_batch_size: int,
    dry_run: bool = False,
    allow_delete: bool = True,
    now: datetime | None = None,
) -> list[HourResult]:
    """归档 [start, end) 内每个整点小时。

    幂等：已标记 deleted 的小时跳过。删除截止点 = now - retention_hours。
    """
    now = (now or datetime.now(UTC)).astimezone(UTC)
    delete_cutoff = aligned_hour(now) - timedelta(hours=retention_hours)
    results: list[HourResult] = []

    conn = await asyncpg.connect(database_url)
    try:
        if not dry_run:
            await ensure_watermark_table(conn)
        for hour_start in iter_hours(start, end):
            if not dry_run and await _already_deleted(conn, hour_start):
                r = HourResult(hour_start=hour_start, skipped=True, reason="已归档删除，跳过")
                results.append(r)
                logger.info("跳过 %s：已归档删除", hour_start.isoformat())
                continue
            try:
                r = await archive_hour(
                    conn,
                    uploader,
                    hour_start,
                    prefix=prefix,
                    max_rows_per_part=max_rows_per_part,
                    delete_cutoff=delete_cutoff,
                    delete_batch_size=delete_batch_size,
                    dry_run=dry_run,
                    allow_delete=allow_delete,
                )
            except Exception as exc:  # noqa: BLE001 — 单小时失败不阻断其余小时
                logger.exception("归档 %s 失败", hour_start.isoformat())
                if not dry_run:
                    await _mark(conn, hour_start, "error", error=str(exc))
                r = HourResult(hour_start=hour_start, reason=f"error: {exc}")
            results.append(r)
            logger.info(
                "小时 %s：行=%d 字节=%d 删除=%d %s",
                hour_start.isoformat(),
                r.row_count,
                r.byte_count,
                r.deleted_rows,
                r.reason,
            )
    finally:
        await conn.close()

    return results





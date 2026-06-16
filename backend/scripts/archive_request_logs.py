#!/usr/bin/env python
"""request_logs 归档 CLI。

子命令：
  run （默认）  归档某区间/某小时到 COS，按保留期删库。无子命令时等同 run。
  list          列出 COS 上已归档对象，并附水位表状态。

用法示例：
  # 跑上一个完整小时（生产默认，systemd 调用）
  python -m scripts.archive_request_logs
  python -m scripts.archive_request_logs run

  # 指定单个小时（UTC），格式 YYYY-MM-DDTHH
  python -m scripts.archive_request_logs run --hour 2026-06-16T08

  # 补跑一段区间（UTC，左闭右开，按整点对齐）
  python -m scripts.archive_request_logs run --from 2026-06-10T00 --to 2026-06-11T00

  # 演练：只导出本地、不上传不删除
  python -m scripts.archive_request_logs run --hour 2026-06-16T08 --dry-run

  # 上传但不删库（首次上线验证用）
  python -m scripts.archive_request_logs run --from 2026-06-10T00 --to 2026-06-11T00 --no-delete

  # 查看已归档：列某天 COS 对象 + 水位状态
  python -m scripts.archive_request_logs list --date 2026-06-16
  python -m scripts.archive_request_logs list --from 2026-06-10T00 --to 2026-06-11T00
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.archive.cos_archiver import (
    CosUploader,
    aligned_hour,
    archive_range,
    summarize_runs,
)
from app.core.config import get_settings

# 仓库根 .env（DATABASE_URL / COS_* 等运行期变量都在这里）。
# 生产由 systemd EnvironmentFile 注入；手动运行时主动加载，省去逐个 export。
_ROOT_ENV = Path(__file__).resolve().parent.parent.parent / ".env"


def _load_root_env() -> None:
    """把根 .env 里尚未设置的 KEY=VALUE 注入 os.environ（不覆盖已有环境变量）。"""
    if not _ROOT_ENV.exists():
        return
    for raw in _ROOT_ENV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = val.strip()


def _parse_hour(s: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H", "%Y-%m-%d %H", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"无法解析时间（用 UTC，如 2026-06-16T08）：{s}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="把 request_logs 按小时归档到腾讯云 COS")
    p.add_argument("-v", "--verbose", action="store_true", help="DEBUG 日志")
    sub = p.add_subparsers(dest="cmd")

    # run（默认）
    pr = sub.add_parser("run", help="归档到 COS 并按保留期删库")
    g = pr.add_mutually_exclusive_group()
    g.add_argument("--hour", type=_parse_hour, help="只归档这一个整点小时（UTC）")
    pr.add_argument("--from", dest="start", type=_parse_hour, help="区间起（UTC，含）")
    pr.add_argument("--to", dest="end", type=_parse_hour, help="区间止（UTC，不含）")
    pr.add_argument("--dry-run", action="store_true", help="只导出到本地临时目录，不上传不删除")
    pr.add_argument("--no-delete", action="store_true", help="上传但不删库")
    pr.add_argument("-v", "--verbose", action="store_true", help="DEBUG 日志")

    # list
    pl = sub.add_parser("list", help="列出已归档的 COS 对象与水位状态")
    pl.add_argument("--date", type=_parse_hour, help="只看这一天（UTC，YYYY-MM-DD）")
    pl.add_argument("--from", dest="start", type=_parse_hour, help="区间起（UTC，含）")
    pl.add_argument("--to", dest="end", type=_parse_hour, help="区间止（UTC，不含）")
    pl.add_argument("--objects", action="store_true", help="同时列出 COS 上每个对象明细")
    pl.add_argument("-v", "--verbose", action="store_true", help="DEBUG 日志")
    return p


def _resolve_range(args: argparse.Namespace) -> tuple[datetime, datetime]:
    if getattr(args, "hour", None):
        return args.hour, args.hour + timedelta(hours=1)
    if args.start and args.end:
        return args.start, args.end
    if args.start or args.end:
        raise SystemExit("--from 与 --to 需同时提供")
    # 默认：上一个完整小时
    prev = aligned_hour(datetime.now(UTC)) - timedelta(hours=1)
    return prev, prev + timedelta(hours=1)


def _make_uploader(settings, *, required: bool) -> CosUploader | None:
    if not settings.cos_secret_id or not settings.cos_secret_key:
        if required:
            print(
                "错误：未配置 COS_SECRET_ID / COS_SECRET_KEY，无法访问 COS。"
                "请填 .env，或对 run 加 --dry-run 仅演练。",
                file=sys.stderr,
            )
        return None
    return CosUploader(
        secret_id=settings.cos_secret_id,
        secret_key=settings.cos_secret_key,
        region=settings.cos_region,
        bucket=settings.cos_bucket,
        endpoint=settings.cos_endpoint,
    )


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    start, end = _resolve_range(args)

    uploader: CosUploader | None = None
    if not args.dry_run:
        uploader = _make_uploader(settings, required=True)
        if uploader is None:
            return 2

    results = await archive_range(
        settings.database_url,
        uploader,
        start,
        end,
        prefix=settings.archive_prefix,
        max_rows_per_part=settings.archive_max_rows_per_part,
        retention_hours=settings.archive_retention_hours,
        delete_batch_size=settings.archive_delete_batch_size,
        dry_run=args.dry_run,
        allow_delete=not args.no_delete,
    )

    rows = sum(r.row_count for r in results)
    deleted = sum(r.deleted_rows for r in results)
    byts = sum(r.byte_count for r in results)
    print(
        f"完成：{len(results)} 个小时，导出 {rows} 行 / {byts} 字节，删除 {deleted} 行。"
        f"区间 [{start:%Y-%m-%dT%H}, {end:%Y-%m-%dT%H}) UTC"
        + ("（dry-run）" if args.dry_run else "")
    )
    return 0


def _fmt_size(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.1f}{unit}" if unit != "B" else f"{int(f)}B"
        f /= 1024
    return f"{f:.1f}TB"


async def _list(args: argparse.Namespace) -> int:
    settings = get_settings()

    # 解析区间
    if args.date:
        start = args.date.replace(hour=0)
        end = start + timedelta(days=1)
    elif args.start and args.end:
        start, end = args.start, args.end
    elif args.start or args.end:
        raise SystemExit("--from 与 --to 需同时提供")
    else:
        start = end = None

    # 1) 水位表状态
    runs = await summarize_runs(settings.database_url, start, end)
    print(f"== 水位表 request_logs_archive_runs（{len(runs)} 条，倒序）==")
    if not runs:
        print("  (空：表尚未创建或区间内无记录)")
    for r in runs:
        print(
            f"  {r['hour_start']:%Y-%m-%dT%H}Z  {r['status']:<9}"
            f"  行={r['row_count']:<7} {_fmt_size(r['byte_count']):>9}"
            f"  片={r['parts']}"
            + (f"  错误={r['error']}" if r.get("error") else "")
        )

    # 2) COS 对象（可选）
    uploader = _make_uploader(settings, required=False)
    if uploader is None:
        print("\n(未配置 COS 凭据，跳过 COS 对象列举)")
        return 0

    prefix = settings.archive_prefix.strip("/") + "/"
    if args.date:
        prefix += f"{start:%Y/%m/%d/}"
    objs = uploader.list_objects(prefix)
    total = sum(o["size"] for o in objs)
    print(f"\n== COS 对象（前缀 {prefix}，{len(objs)} 个，合计 {_fmt_size(total)}）==")
    if args.objects:
        for o in objs:
            print(f"  {o['key']}  {_fmt_size(o['size']):>9}  {o['last_modified']}")
    else:
        # 默认按小时目录聚合，避免刷屏
        from collections import defaultdict

        agg: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for o in objs:
            hour_dir = o["key"].rsplit("/", 1)[0]
            agg[hour_dir][0] += 1
            agg[hour_dir][1] += o["size"]
        for hour_dir in sorted(agg):
            cnt, sz = agg[hour_dir]
            print(f"  {hour_dir}/  片={cnt}  {_fmt_size(sz):>9}")
        if objs:
            print("  （加 --objects 看每个对象明细）")
    return 0


def main() -> None:
    args = _build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _load_root_env()
    if args.cmd == "list":
        raise SystemExit(asyncio.run(_list(args)))
    # cmd 为 "run" 或 None（无子命令）：补齐 run 所需默认值
    for attr, default in (("hour", None), ("start", None), ("end", None),
                          ("dry_run", False), ("no_delete", False)):
        if not hasattr(args, attr):
            setattr(args, attr, default)
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()

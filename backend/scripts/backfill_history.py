#!/usr/bin/env python
"""历史 request_logs 补传：按天逐批归档到 COS，48h 外的传完即删。

特性：
- 串行逐天跑，避开每小时 03-07 分（systemd timer 在 05 分跑，错峰）
- 幂等：靠水位表，跑挂重跑自动跳过已完成小时
- 进度与耗时打到 stdout，可重定向到日志 tail

用法：
  cd /home/wangzhong/ai-studio/backend
  nohup ../.venv/bin/python -m scripts.backfill_history >> /tmp/backfill.log 2>&1 &
  tail -f /tmp/backfill.log
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, date, datetime, timedelta

from app.archive.cos_archiver import CosUploader, archive_range
from app.core.config import get_settings

from scripts.archive_request_logs import _load_root_env

START_DAY = date(2026, 5, 10)


def _now() -> str:
    return datetime.now(UTC).strftime("%F %T")


async def main() -> None:
    _load_root_env()
    settings = get_settings()
    if not settings.cos_secret_id or not settings.cos_secret_key:
        raise SystemExit("未配置 COS 凭据，无法补传")

    uploader = CosUploader(
        secret_id=settings.cos_secret_id,
        secret_key=settings.cos_secret_key,
        region=settings.cos_region,
        bucket=settings.cos_bucket,
        endpoint=settings.cos_endpoint,
    )

    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    print("=" * 50)
    print(f"补传开始 {_now()} UTC")
    print(f"区间 {START_DAY}T00 .. {end:%Y-%m-%dT%H} UTC")
    print("=" * 50, flush=True)

    cur = datetime(START_DAY.year, START_DAY.month, START_DAY.day, tzinfo=UTC)
    while cur < end:
        nxt = min(cur + timedelta(days=1), end)

        # 错峰：整点 03-07 分内等到过去，避开 systemd timer（05 分）
        minute = datetime.now(UTC).minute
        if 3 <= minute <= 7:
            print(f"[{_now()}] 接近整点（{minute} 分），等 90s 错峰...", flush=True)
            time.sleep(90)

        print(f"[{_now()}] 补传 {cur:%Y-%m-%dT%H} .. {nxt:%Y-%m-%dT%H}", flush=True)
        t0 = time.monotonic()
        results = await archive_range(
            settings.database_url,
            uploader,
            cur,
            nxt,
            prefix=settings.archive_prefix,
            max_rows_per_part=settings.archive_max_rows_per_part,
            retention_hours=settings.archive_retention_hours,
            delete_batch_size=settings.archive_delete_batch_size,
        )
        rows = sum(r.row_count for r in results)
        deleted = sum(r.deleted_rows for r in results)
        byts = sum(r.byte_count for r in results)
        errs = [r for r in results if r.reason.startswith("error")]
        dt = time.monotonic() - t0
        print(
            f"[{_now()}] 本天完成：{len(results)} 小时，导出 {rows} 行 / "
            f"{byts / 1e6:.1f}MB，删除 {deleted} 行，耗时 {dt:.0f}s"
            + (f"，⚠️ {len(errs)} 个小时出错" if errs else ""),
            flush=True,
        )
        cur = nxt

    print("=" * 50)
    print(f"补传完成 {_now()} UTC", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

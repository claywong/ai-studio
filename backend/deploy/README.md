# request_logs → 腾讯云 COS 归档

每小时把 `request_logs` 表中**上一个完整小时**的数据导出为 `JSONL+gzip` 上传到腾讯云
COS，校验上传成功后，删除库内**超过保留期（默认 48 小时）**的已归档数据，控制表体积。

## 组成

- `app/archive/cos_archiver.py` — 核心：区间对齐、流式 gzip 导出、COS 上传+回读校验、
  水位表 `request_logs_archive_runs`、安全分批删除。
- `scripts/archive_request_logs.py` — CLI 入口（`-m scripts.archive_request_logs`）。
- `deploy/request-logs-archiver.{service,timer}` — systemd 单元。

## COS 对象布局

```
request-logs/YYYY/MM/DD/HH/part-0001.jsonl.gz
```

每行一条 JSON：`request_id / session_id / user_id / created_at(UTC ISO) / request_body / response_body`。
单分片默认上限 5 万行（`ARCHIVE_MAX_ROWS_PER_PART`），超出自动切 `part-0002…`。

## 配置（根 `.env`）

```
COS_SECRET_ID=          # 必填
COS_SECRET_KEY=         # 必填
COS_REGION=ap-shanghai
COS_BUCKET=your-bucket-appid
COS_ENDPOINT=           # 留空由 SDK 自动拼接
ARCHIVE_RETENTION_HOURS=48
ARCHIVE_PREFIX=request-logs
ARCHIVE_MAX_ROWS_PER_PART=50000
```

## 手动用法

```bash
cd /home/wangzhong/ai-studio/backend
PY=/home/wangzhong/ai-studio/.venv/bin/python

# 演练：只导出本地，不上传不删除
$PY -m scripts.archive_request_logs run --hour 2026-06-16T08 --dry-run

# 上传但不删库（首次上线验证）
$PY -m scripts.archive_request_logs run --from 2026-06-10T00 --to 2026-06-11T00 --no-delete

# 默认：归档上一个完整小时并按保留期清理（systemd 调用）
$PY -m scripts.archive_request_logs        # 等同 run，无参数

# 查看已归档：水位表状态 + COS 对象（按小时目录聚合）
$PY -m scripts.archive_request_logs list --date 2026-06-16
$PY -m scripts.archive_request_logs list --from 2026-06-10T00 --to 2026-06-11T00 --objects
```

时间一律按 **UTC** 整点，区间左闭右开。

## 对象组织与重跑行为

- 布局：`{prefix}/YYYY/MM/DD/HH/part-NNNN.jsonl.gz`，按 UTC 整点一个目录。
- 同一小时**重跑会覆盖同名对象**（key 确定性），不会产生多份。
- 若重跑时本次片数少于上次，目录里编号更大的**残留旧分片会被自动清理**，保证目录干净。

## 安全保证

- 删除前强制三条件全满足：该小时已 `uploaded` + COS 回读大小/ETag 一致 + 整个小时早于
  `now - ARCHIVE_RETENTION_HOURS`。任一不满足则跳过删除。
- 水位表保证幂等：已 `deleted` 的小时重跑直接跳过；失败小时标 `error`，可重跑。
- 删除分批进行（默认每批 5000 行），不长时间持锁。

## 安装 systemd 定时任务

```bash
sudo cp /home/wangzhong/ai-studio/backend/deploy/request-logs-archiver.service /etc/systemd/system/
sudo cp /home/wangzhong/ai-studio/backend/deploy/request-logs-archiver.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now request-logs-archiver.timer

# 查看下次触发时间与状态
systemctl list-timers request-logs-archiver.timer
systemctl status request-logs-archiver.service
journalctl -u request-logs-archiver.service -n 50
```

## 上线建议

1. 先填好 `.env` 里的 `COS_SECRET_ID/KEY`。
2. 用 `--dry-run` 跑一个小时确认导出正常。
3. 用 `--no-delete` 跑一段区间，去 COS 控制台核对对象内容无误。
4. 历史 ~2.8GB 数据可用 `--from/--to --no-delete` 分批补传，再开 timer 让其按保留期逐步清理。
5. 启用 timer，按默认每小时第 5 分钟自动运行。

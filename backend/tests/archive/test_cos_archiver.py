"""tests for app.archive.cos_archiver"""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime, timedelta, timezone

import pytest
from app.archive import cos_archiver as m

# ----------------------------- 纯函数 -----------------------------

def test_aligned_hour_floors_to_utc_hour():
    dt = datetime(2026, 6, 16, 8, 37, 12, 500, tzinfo=UTC)
    assert m.aligned_hour(dt) == datetime(2026, 6, 16, 8, 0, 0, tzinfo=UTC)


def test_aligned_hour_converts_timezone():
    # +08:00 的 08:30 == UTC 00:30 -> 对齐到 UTC 00:00
    tz8 = timezone(timedelta(hours=8))
    dt = datetime(2026, 6, 16, 8, 30, tzinfo=tz8)
    assert m.aligned_hour(dt) == datetime(2026, 6, 16, 0, 0, tzinfo=UTC)


def test_iter_hours_half_open():
    start = datetime(2026, 6, 16, 8, 0, tzinfo=UTC)
    end = datetime(2026, 6, 16, 11, 0, tzinfo=UTC)
    hours = list(m.iter_hours(start, end))
    assert hours == [
        datetime(2026, 6, 16, 8, 0, tzinfo=UTC),
        datetime(2026, 6, 16, 9, 0, tzinfo=UTC),
        datetime(2026, 6, 16, 10, 0, tzinfo=UTC),
    ]


def test_iter_hours_empty_when_equal():
    h = datetime(2026, 6, 16, 8, 0, tzinfo=UTC)
    assert list(m.iter_hours(h, h)) == []


def test_object_key_layout():
    h = datetime(2026, 6, 16, 8, 0, tzinfo=UTC)
    assert m._object_key("request-logs", h, 1) == "request-logs/2026/06/16/08/part-0001.jsonl.gz"
    assert m._object_key("/p/", h, 23) == "p/2026/06/16/08/part-0023.jsonl.gz"


def test_row_to_json_roundtrip():
    row = {
        "request_id": "r1",
        "session_id": "s1",
        "user_id": 42,
        "email": "a@b.com",
        "request_body": "你好",
        "response_body": None,
        "created_at": datetime(2026, 6, 16, 8, 30, tzinfo=UTC),
    }
    obj = json.loads(m._row_to_json(row))
    assert obj["request_id"] == "r1"
    assert obj["user_id"] == 42
    assert obj["email"] == "a@b.com"
    assert obj["request_body"] == "你好"
    assert obj["response_body"] is None
    assert obj["created_at"].startswith("2026-06-16T08:30")


# ----------------------------- 伪 asyncpg / COS -----------------------------

class _FakeTxn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def __aiter__(self):
        async def gen():
            for r in self._rows:
                yield r
        return gen()


class FakeConn:
    """够用的 asyncpg.Connection 替身。

    rows_by_hour: {hour_start: [row dict, ...]}（row 用 dict 即可，模块按 key 取值）。
    """

    def __init__(self, rows_by_hour):
        self.rows_by_hour = {k: list(v) for k, v in rows_by_hour.items()}
        self.watermark = {}  # hour_start -> status row dict
        self.executed = []

    def transaction(self):
        return _FakeTxn()

    def cursor(self, sql, hour_start, hour_end):
        return _FakeCursor(self.rows_by_hour.get(hour_start, []))

    async def execute(self, sql, *args):
        self.executed.append((sql, args))
        s = sql.strip().upper()
        if s.startswith("CREATE TABLE"):
            return "CREATE TABLE"
        if s.startswith("INSERT INTO REQUEST_LOGS_ARCHIVE_RUNS"):
            hour_start, status, row_count, byte_count, keys, error = args
            self.watermark[hour_start] = {
                "status": status, "row_count": row_count,
                "byte_count": byte_count, "object_keys": keys, "error": error,
            }
            return "INSERT 0 1"
        if s.startswith("DELETE FROM REQUEST_LOGS"):
            hour_start, hour_end, limit = args
            rows = self.rows_by_hour.get(hour_start, [])
            n = min(limit, len(rows))
            self.rows_by_hour[hour_start] = rows[n:]
            return f"DELETE {n}"
        return "OK"

    async def fetchval(self, sql, *args):
        s = sql.strip().upper()
        if s.startswith("SELECT STATUS FROM REQUEST_LOGS_ARCHIVE_RUNS"):
            hour_start = args[0]
            row = self.watermark.get(hour_start)
            return row["status"] if row else None
        return None

    async def close(self):
        pass


class FakeUploader:
    """模拟 COS：put_file 计算真实 MD5/大小并缓存，head 回读一致值。

    fail_keys 里的 key 会让 head 返回错误大小，触发校验失败。
    """

    def __init__(self, fail_keys=None):
        self.objects = {}  # key -> (size, md5)
        self.put_calls = []
        self.deleted_objects = []
        self.fail_keys = set(fail_keys or [])

    def put_file(self, local_path, key):
        import os
        size = os.path.getsize(local_path)
        md5 = m._md5_hex(local_path)
        self.objects[key] = (size, md5)
        self.put_calls.append(key)
        return md5

    def head(self, key):
        size, _ = self.objects[key]
        if key in self.fail_keys:
            size = size + 1  # 故意制造大小不一致
        return {"Content-Length": str(size)}

    def list_objects(self, prefix):
        out = [
            {"key": k, "size": v[0], "last_modified": ""}
            for k, v in self.objects.items()
            if k.startswith(prefix)
        ]
        out.sort(key=lambda o: o["key"])
        return out

    def delete_object(self, key):
        self.objects.pop(key, None)
        self.deleted_objects.append(key)


def _row(rid, hour, minute=0, user_id=1):
    return {
        "request_id": rid,
        "session_id": "sess",
        "user_id": user_id,
        "email": f"u{user_id}@example.com",
        "request_body": "req-" + rid,
        "response_body": "resp-" + rid,
        "created_at": hour.replace(minute=minute),
    }


H8 = datetime(2026, 6, 16, 8, 0, tzinfo=UTC)
H9 = datetime(2026, 6, 16, 9, 0, tzinfo=UTC)
# now 设为很久以后，保证保留期早已过，可删
NOW_LATE = datetime(2026, 6, 30, 0, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_export_splits_into_parts(tmp_path):
    conn = FakeConn({H8: [_row(f"r{i}", H8) for i in range(5)]})
    paths, total = await m._export_hour_parts(conn, H8, str(tmp_path), max_rows_per_part=2)
    assert total == 5
    assert len(paths) == 3  # 2 + 2 + 1
    # 校验第一片内容确为 gzip JSONL，且每行可解析
    with gzip.open(paths[0], "rb") as f:
        lines = f.read().decode().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["request_id"] == "r0"


@pytest.mark.asyncio
async def test_rerun_cleans_up_stale_parts(tmp_path, monkeypatch):
    """重跑时若本次片数变少，旧的多余分片应被清掉。"""
    monkeypatch.setattr(m.tempfile, "TemporaryDirectory",
                        lambda *a, **k: _TmpDir(tmp_path))
    conn = FakeConn({H8: [_row(f"r{i}", H8, minute=i) for i in range(2)]})
    monkeypatch.setattr(m.asyncpg, "connect", _connect_returning(conn))

    up = FakeUploader()
    # 预置上次遗留的 part-0002 / part-0003（本次只会产 1 片）
    up.objects["request-logs/2026/06/16/08/part-0002.jsonl.gz"] = (10, "x")
    up.objects["request-logs/2026/06/16/08/part-0003.jsonl.gz"] = (10, "y")

    res = await m.archive_range(
        "fake://db", up, H8, H9,
        prefix="request-logs", max_rows_per_part=50000,
        retention_hours=48, delete_batch_size=1000,
        now=H9 + timedelta(hours=1),  # 保留期内，不删库，专测清理
    )
    assert res[0].object_keys == ["request-logs/2026/06/16/08/part-0001.jsonl.gz"]
    assert sorted(up.deleted_objects) == [
        "request-logs/2026/06/16/08/part-0002.jsonl.gz",
        "request-logs/2026/06/16/08/part-0003.jsonl.gz",
    ]
    # 目录里只剩 part-0001
    assert list(up.objects) == ["request-logs/2026/06/16/08/part-0001.jsonl.gz"]



@pytest.mark.asyncio
async def test_archive_hour_uploads_and_deletes_after_retention(tmp_path, monkeypatch):
    monkeypatch.setattr(m.tempfile, "TemporaryDirectory",
                        lambda *a, **k: _TmpDir(tmp_path))
    conn = FakeConn({H8: [_row(f"r{i}", H8, minute=i) for i in range(3)]})

    async def fake_connect(url):
        return conn
    monkeypatch.setattr(m.asyncpg, "connect", fake_connect)

    up = FakeUploader()
    res = await m.archive_range(
        "fake://db", up, H8, H9,
        prefix="request-logs", max_rows_per_part=50000,
        retention_hours=48, delete_batch_size=1000,
        now=NOW_LATE,
    )
    r = res[0]
    assert r.row_count == 3
    assert r.deleted_rows == 3
    assert r.object_keys == ["request-logs/2026/06/16/08/part-0001.jsonl.gz"]
    assert up.put_calls == r.object_keys
    assert conn.rows_by_hour[H8] == []  # 已删空
    assert conn.watermark[H8]["status"] == "deleted"


@pytest.mark.asyncio
async def test_within_retention_uploads_but_keeps_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(m.tempfile, "TemporaryDirectory",
                        lambda *a, **k: _TmpDir(tmp_path))
    conn = FakeConn({H8: [_row(f"r{i}", H8, minute=i) for i in range(3)]})
    monkeypatch.setattr(m.asyncpg, "connect", _connect_returning(conn))
    up = FakeUploader()
    # now 仅比 H9 晚 1 小时，远不到 48h 保留期 -> 不删
    now = H9 + timedelta(hours=1)
    res = await m.archive_range(
        "fake://db", up, H8, H9,
        prefix="request-logs", max_rows_per_part=50000,
        retention_hours=48, delete_batch_size=1000,
        now=now,
    )
    r = res[0]
    assert r.row_count == 3
    assert r.deleted_rows == 0
    assert len(conn.rows_by_hour[H8]) == 3  # 保留
    assert conn.watermark[H8]["status"] == "uploaded"


@pytest.mark.asyncio
async def test_verify_failure_skips_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(m.tempfile, "TemporaryDirectory",
                        lambda *a, **k: _TmpDir(tmp_path))
    conn = FakeConn({H8: [_row(f"r{i}", H8, minute=i) for i in range(3)]})
    monkeypatch.setattr(m.asyncpg, "connect", _connect_returning(conn))
    key = "request-logs/2026/06/16/08/part-0001.jsonl.gz"
    up = FakeUploader(fail_keys={key})
    res = await m.archive_range(
        "fake://db", up, H8, H9,
        prefix="request-logs", max_rows_per_part=50000,
        retention_hours=48, delete_batch_size=1000,
        now=NOW_LATE,
    )
    r = res[0]
    assert r.deleted_rows == 0
    assert len(conn.rows_by_hour[H8]) == 3  # 校验失败，绝不删
    assert conn.watermark[H8]["status"] == "error"


@pytest.mark.asyncio
async def test_idempotent_skips_already_deleted(tmp_path, monkeypatch):
    monkeypatch.setattr(m.tempfile, "TemporaryDirectory",
                        lambda *a, **k: _TmpDir(tmp_path))
    conn = FakeConn({H8: []})
    conn.watermark[H8] = {"status": "deleted"}
    monkeypatch.setattr(m.asyncpg, "connect", _connect_returning(conn))
    up = FakeUploader()
    res = await m.archive_range(
        "fake://db", up, H8, H9,
        prefix="request-logs", max_rows_per_part=50000,
        retention_hours=48, delete_batch_size=1000,
        now=NOW_LATE,
    )
    assert res[0].skipped is True
    assert up.put_calls == []  # 不再上传


@pytest.mark.asyncio
async def test_empty_hour_marked_deleted_no_upload(tmp_path, monkeypatch):
    monkeypatch.setattr(m.tempfile, "TemporaryDirectory",
                        lambda *a, **k: _TmpDir(tmp_path))
    conn = FakeConn({H8: []})
    monkeypatch.setattr(m.asyncpg, "connect", _connect_returning(conn))
    up = FakeUploader()
    res = await m.archive_range(
        "fake://db", up, H8, H9,
        prefix="request-logs", max_rows_per_part=50000,
        retention_hours=48, delete_batch_size=1000,
        now=NOW_LATE,
    )
    assert res[0].row_count == 0
    assert up.put_calls == []
    assert conn.watermark[H8]["status"] == "deleted"


def _connect_returning(conn):
    async def _connect(url):
        return conn
    return _connect


class _TmpDir:
    """让 archive_range 用我们指定的临时目录（可检查产物）。"""
    def __init__(self, path):
        self.path = str(path)

    def __enter__(self):
        return self.path

    def __exit__(self, *a):
        return False



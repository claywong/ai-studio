-- 优化报表查询的索引
-- 针对 /admin/reports/accounts 和 /admin/reports/account-groups 接口

-- 1. 创建覆盖索引，包含报表查询常用字段
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_usage_logs_reports_covering
ON usage_logs (created_at, account_id, model)
INCLUDE (
    input_tokens,
    output_tokens,
    cache_creation_tokens,
    cache_read_tokens,
    account_stats_cost,
    total_cost,
    account_rate_multiplier,
    first_token_ms,
    duration_ms
)
WHERE created_at >= NOW() - INTERVAL '90 days';

-- 2. 为 account-groups 查询创建优化索引
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_usage_logs_group_reports
ON usage_logs (created_at, group_id, model)
INCLUDE (
    input_tokens,
    output_tokens,
    cache_creation_tokens,
    cache_read_tokens,
    actual_cost,
    first_token_ms,
    duration_ms,
    account_id
)
WHERE created_at >= NOW() - INTERVAL '90 days';

-- 查看索引创建进度
SELECT
    now()::TIME as check_time,
    phase,
    round(100.0 * blocks_done / nullif(blocks_total, 0), 2) AS "% complete"
FROM pg_stat_progress_create_index;

-- 创建每日账号统计物化视图
-- 预计算每天的账号统计数据，大幅提升查询速度

CREATE MATERIALIZED VIEW IF NOT EXISTS daily_account_stats AS
WITH model_stats AS (
    SELECT
        (ul.created_at AT TIME ZONE 'Asia/Shanghai')::date AS stat_date,
        ul.account_id,
        COALESCE(a.name, '未知账号-' || ul.account_id::text) AS account_name,
        COALESCE(REGEXP_REPLACE(a.name, '[-_].*$', ''), '已删除') AS grp,
        COALESCE(a.platform, '') AS platform,
        COALESCE(a.status, 'deleted') AS status,
        ul.model,
        COUNT(ul.id) AS requests,
        COALESCE(SUM(COALESCE(ul.account_stats_cost, ul.total_cost) * COALESCE(ul.account_rate_multiplier, 1.0)), 0) AS total_cost,
        COALESCE(SUM(ul.input_tokens), 0) AS input_tokens,
        COALESCE(SUM(ul.output_tokens), 0) AS output_tokens,
        COALESCE(SUM(ul.cache_creation_tokens), 0) AS cache_creation_tokens,
        COALESCE(SUM(ul.cache_read_tokens), 0) AS cache_read_tokens,
        ROUND(AVG(ul.first_token_ms) FILTER (WHERE ul.first_token_ms > 0))::int AS ttft_avg,
        COALESCE(SUM(ul.first_token_ms) FILTER (WHERE ul.first_token_ms > 0), 0)::numeric AS ttft_sum,
        COUNT(*) FILTER (WHERE ul.first_token_ms > 0) AS ttft_count,
        ROUND(AVG(
            CASE WHEN ul.duration_ms > 0
            THEN ul.output_tokens::numeric / (ul.duration_ms / 1000.0) END
        )::numeric, 2) AS otps_avg,
        COALESCE(SUM(
            CASE WHEN ul.duration_ms > 0
            THEN ul.output_tokens::numeric / (ul.duration_ms / 1000.0) END
        ), 0)::numeric AS otps_sum,
        COUNT(*) FILTER (WHERE ul.duration_ms > 0) AS otps_count
    FROM usage_logs ul
    LEFT JOIN accounts a ON a.id = ul.account_id
    WHERE ul.created_at >= NOW() - INTERVAL '90 days'
    GROUP BY stat_date, ul.account_id, a.name, a.platform, a.status, ul.model
)
SELECT
    stat_date,
    account_id,
    account_name,
    grp,
    platform,
    status,
    model,
    requests,
    total_cost,
    input_tokens,
    output_tokens,
    cache_creation_tokens,
    cache_read_tokens,
    ttft_avg,
    ttft_sum,
    ttft_count,
    otps_avg,
    otps_sum,
    otps_count,
    CASE
        WHEN cache_read_tokens + input_tokens + cache_creation_tokens > 0
        THEN ROUND(cache_read_tokens::numeric / (cache_read_tokens + input_tokens + cache_creation_tokens) * 100, 1)
        ELSE NULL
    END AS cache_hit_rate,
    CASE WHEN requests > 0
        THEN ROUND(total_cost::numeric / requests, 8)
        ELSE NULL
    END AS cost_avg
FROM model_stats;

-- 创建索引加速物化视图查询
CREATE INDEX IF NOT EXISTS idx_daily_account_stats_date
ON daily_account_stats(stat_date);

CREATE INDEX IF NOT EXISTS idx_daily_account_stats_account_date
ON daily_account_stats(account_id, stat_date);

CREATE INDEX IF NOT EXISTS idx_daily_account_stats_date_account_model
ON daily_account_stats(stat_date, account_id, model);

-- 刷新物化视图的函数（每天凌晨定时执行）
CREATE OR REPLACE FUNCTION refresh_daily_account_stats()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY daily_account_stats;
END;
$$ LANGUAGE plpgsql;

-- 注释：需要配置 cron 任务每天凌晨刷新
-- 例如：SELECT cron.schedule('refresh-daily-stats', '0 1 * * *', 'SELECT refresh_daily_account_stats()');

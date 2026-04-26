# 数据库表结构说明

数据库使用 **PostgreSQL**，ORM 框架为 **Ent**（`entgo.io/ent`）。所有表均支持软删除（`deleted_at` 字段），部分例外见各表说明。

---

## users（用户表）

存储系统注册用户信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `email` | string | 邮箱（唯一，软删除后可复用） |
| `password_hash` | string | 密码哈希 |
| `role` | string | 角色：`user` / `admin` |
| `balance` | decimal | 账户余额（USD） |
| `concurrency` | int | 并发限制（默认 5） |
| `status` | string | 状态：`active` / `banned` / `disabled` |
| `username` | string | 用户名（可选） |
| `notes` | string | 管理员备注 |
| `totp_secret_encrypted` | string | 加密存储的 TOTP 密钥 |
| `totp_enabled` | bool | 是否启用 TOTP |
| `totp_enabled_at` | *time | TOTP 启用时间 |
| `signup_source` | string | 注册来源：`email` / `linuxdo` / `wechat` / `oidc` |
| `last_login_at` | *time | 最后登录时间 |
| `last_active_at` | *time | 最后活跃时间 |
| `balance_notify_enabled` | bool | 是否启用余额通知 |
| `balance_notify_threshold_type` | string | 通知阈值类型：`fixed` / `percentage` |
| `balance_notify_threshold` | *decimal | 通知阈值 |
| `balance_notify_extra_emails` | string | 额外通知邮箱（JSON 数组） |
| `total_recharged` | decimal | 累计充值金额 |
| `rpm_limit` | int | RPM 限制（0 = 不限制） |
| `created_at` | time | 创建时间 |
| `updated_at` | time | 更新时间 |
| `deleted_at` | *time | 软删除时间 |

---

## api_keys（API Key 表）

存储用户创建的 API Key，用于网关调用认证。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `user_id` | int64 | 关联用户 ID |
| `key` | string | Key 值（唯一） |
| `name` | string | Key 名称 |
| `group_id` | *int64 | 绑定分组 ID（可选） |
| `status` | string | 状态：`active` / `expired` / `quota_exhausted` / `disabled` |
| `last_used_at` | *time | 最后使用时间 |
| `ip_whitelist` | []string | IP 白名单（JSON 数组） |
| `ip_blacklist` | []string | IP 黑名单（JSON 数组） |
| `quota` | decimal | 配额上限（USD，0 = 无限制） |
| `quota_used` | decimal | 已用配额 |
| `expires_at` | *time | 过期时间 |
| `rate_limit_5h` | decimal | 5 小时速率限制（USD） |
| `rate_limit_1d` | decimal | 1 天速率限制（USD） |
| `rate_limit_7d` | decimal | 7 天速率限制（USD） |
| `usage_5h` | decimal | 5 小时已用 |
| `usage_1d` | decimal | 1 天已用 |
| `usage_7d` | decimal | 7 天已用 |
| `window_5h_start` | *time | 5 小时窗口开始时间 |
| `window_1d_start` | *time | 1 天窗口开始时间 |
| `window_7d_start` | *time | 7 天窗口开始时间 |
| `created_at` | time | 创建时间 |
| `updated_at` | time | 更新时间 |
| `deleted_at` | *time | 软删除时间 |

---

## groups（分组表）

管理用户分组，控制计费倍率、订阅限额、模型路由等。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `name` | string | 分组名（唯一，软删除后可复用） |
| `description` | string | 描述 |
| `rate_multiplier` | float64 | 计费倍率（默认 1.0） |
| `is_exclusive` | bool | 是否独占 |
| `status` | string | 状态：`active` / `disabled` |
| `platform` | string | 平台：`anthropic` / `google` / `openai` |
| `subscription_type` | string | 订阅类型：`standard` / `free` |
| `daily_limit_usd` | *decimal | 每日用量上限（USD） |
| `weekly_limit_usd` | *decimal | 每周用量上限（USD） |
| `monthly_limit_usd` | *decimal | 每月用量上限（USD） |
| `default_validity_days` | int | 默认有效天数（默认 30） |
| `image_price_1k` | *decimal | 1K 分辨率图片单价 |
| `image_price_2k` | *decimal | 2K 分辨率图片单价 |
| `image_price_4k` | *decimal | 4K 分辨率图片单价 |
| `claude_code_only` | bool | 仅允许 Claude Code 客户端 |
| `fallback_group_id` | *int64 | 降级分组 ID |
| `fallback_group_id_on_invalid_request` | *int64 | 无效请求降级分组 ID |
| `model_routing` | JSONB | 模型路由规则（map[string][]int64） |
| `model_routing_enabled` | bool | 是否启用模型路由 |
| `mcp_xml_inject` | bool | 是否注入 MCP XML |
| `supported_model_scopes` | []string | 支持的模型系列 |
| `sort_order` | int | 排序值 |
| `allow_messages_dispatch` | bool | 允许 /v1/messages 调度 |
| `require_oauth_only` | bool | 仅非 API Key 账号 |
| `require_privacy_set` | bool | 需要设置隐私 |
| `default_mapped_model` | string | 默认映射模型 |
| `messages_dispatch_model_config` | JSONB | 调度模型配置 |
| `rpm_limit` | int | RPM 限制（0 = 不限制） |
| `created_at` | time | 创建时间 |
| `updated_at` | time | 更新时间 |
| `deleted_at` | *time | 软删除时间 |

---

## accounts（AI 账户表）

存储对接的 AI 平台账号（Claude、Gemini、OpenAI 等）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `name` | string | 账户名称 |
| `notes` | string | 备注 |
| `platform` | string | 平台：`claude` / `gemini` / `openai` |
| `type` | string | 类型：`api_key` / `oauth` / `cookie` |
| `credentials` | JSONB | 凭证数据（加密存储） |
| `extra` | JSONB | 扩展数据 |
| `proxy_id` | *int64 | 关联代理 ID |
| `concurrency` | int | 并发限制（默认 3） |
| `load_factor` | *int | 负载因子 |
| `priority` | int | 优先级（默认 50） |
| `rate_multiplier` | float64 | 账号计费倍率 |
| `status` | string | 状态：`active` / `error` / `disabled` |
| `error_message` | string | 最近错误信息 |
| `last_used_at` | *time | 最后使用时间 |
| `expires_at` | *time | 账号过期时间 |
| `auto_pause_on_expired` | bool | 过期自动暂停 |
| `schedulable` | bool | 是否可被调度器选中 |
| `rate_limited_at` | *time | 被限速时间 |
| `rate_limit_reset_at` | *time | 限速解除时间 |
| `overload_until` | *time | 过载状态解除时间 |
| `temp_unschedulable_until` | *time | 临时不可调度截止时间 |
| `temp_unschedulable_reason` | string | 临时不可调度原因 |
| `session_window_start` | *time | 会话窗口开始时间 |
| `session_window_end` | *time | 会话窗口结束时间 |
| `session_window_status` | string | 会话窗口状态 |
| `created_at` | time | 创建时间 |
| `updated_at` | time | 更新时间 |
| `deleted_at` | *time | 软删除时间 |

---

## user_subscriptions（用户订阅表）

记录用户与分组之间的订阅关系及用量限额。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `user_id` | int64 | 用户 ID |
| `group_id` | int64 | 分组 ID |
| `starts_at` | time | 订阅开始时间 |
| `expires_at` | time | 订阅过期时间 |
| `status` | string | 状态：`active` / `expired` / `cancelled` |
| `daily_window_start` | *time | 每日窗口开始时间 |
| `weekly_window_start` | *time | 每周窗口开始时间 |
| `monthly_window_start` | *time | 每月窗口开始时间 |
| `daily_usage_usd` | decimal | 当日已用（USD） |
| `weekly_usage_usd` | decimal | 当周已用（USD） |
| `monthly_usage_usd` | decimal | 当月已用（USD） |
| `assigned_by` | *int64 | 分配者用户 ID |
| `assigned_at` | time | 分配时间 |
| `notes` | string | 备注 |
| `created_at` | time | 创建时间 |
| `updated_at` | time | 更新时间 |
| `deleted_at` | *time | 软删除时间 |

---

## usage_logs（使用日志表）

记录每次 API 调用的 Token 消耗和费用，为高频写入表。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `user_id` | int64 | 用户 ID |
| `api_key_id` | int64 | API Key ID |
| `account_id` | int64 | AI 账户 ID |
| `request_id` | string | 唯一请求 ID |
| `model` | string | 实际使用的模型名 |
| `requested_model` | *string | 客户端请求的模型名 |
| `upstream_model` | *string | 上游返回的模型名 |
| `channel_id` | *int64 | 渠道 ID |
| `model_mapping_chain` | *string | 模型映射链 |
| `billing_tier` | *string | 计费层级 |
| `billing_mode` | *string | 计费模式：`token` / `per_request` / `image` |
| `group_id` | *int64 | 分组 ID |
| `subscription_id` | *int64 | 订阅 ID |
| `input_tokens` | int | 输入 Token 数 |
| `output_tokens` | int | 输出 Token 数 |
| `cache_creation_tokens` | int | 缓存创建 Token 数 |
| `cache_read_tokens` | int | 缓存读取 Token 数 |
| `cache_creation_5m_tokens` | int | 5 分钟缓存创建 Token 数 |
| `cache_creation_1h_tokens` | int | 1 小时缓存创建 Token 数 |
| `input_cost` | decimal | 输入费用（USD） |
| `output_cost` | decimal | 输出费用（USD） |
| `cache_creation_cost` | decimal | 缓存创建费用 |
| `cache_read_cost` | decimal | 缓存读取费用 |
| `total_cost` | decimal | 原始总费用 |
| `actual_cost` | decimal | 应用倍率后的实际费用 |
| `rate_multiplier` | float64 | 分组倍率快照 |
| `account_rate_multiplier` | *float64 | 账号倍率快照 |
| `billing_type` | int8 | 计费类型枚举 |
| `stream` | bool | 是否流式响应 |
| `duration_ms` | *int | 请求总耗时（毫秒） |
| `first_token_ms` | *int | 首 Token 延迟（毫秒） |
| `user_agent` | *string | 客户端 User-Agent |
| `ip_address` | *string | 客户端 IP |
| `image_count` | int | 生成图片数量 |
| `image_size` | *string | 图片尺寸 |
| `cache_ttl_overridden` | bool | 是否覆盖缓存 TTL |
| `created_at` | time | 创建时间（不可修改） |

> 注：`usage_logs` 无 `updated_at` 和 `deleted_at`，为只追加写入。

---

## auth_identities（认证身份表）

存储用户的各种登录身份（邮箱、OAuth 等）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `user_id` | int64 | 关联用户 ID |
| `provider_type` | string | 提供商类型：`email` / `linuxdo` / `wechat` / `oidc` |
| `provider_key` | string | 提供商唯一标识 |
| `provider_subject` | string | OAuth Subject |
| `verified_at` | *time | 验证时间 |
| `issuer` | *string | OIDC Issuer |
| `metadata` | JSONB | 扩展元数据 |
| `created_at` | time | 创建时间 |
| `updated_at` | time | 更新时间 |

---

## pending_auth_sessions（待处理认证会话表）

存储 OAuth 流程中的临时会话状态，用于多步骤认证流程。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `session_token` | string | 会话令牌（唯一） |
| `intent` | string | 意图：`login` / `bind_current_user` / `adopt_existing_user_by_email` |
| `provider_type` | string | 提供商类型 |
| `provider_key` | string | 提供商标识 |
| `provider_subject` | string | OAuth Subject |
| `target_user_id` | *int64 | 目标用户 ID |
| `redirect_to` | string | 完成后跳转 URL |
| `resolved_email` | string | 解析出的邮箱 |
| `registration_password_hash` | string | 注册密码哈希 |
| `upstream_identity_claims` | JSONB | 上游身份 Claims |
| `local_flow_state` | JSONB | 本地流程状态 |
| `browser_session_key` | string | 浏览器会话 Key |
| `completion_code_hash` | string | 完成码哈希 |
| `completion_code_expires_at` | *time | 完成码过期时间 |
| `email_verified_at` | *time | 邮箱验证时间 |
| `password_verified_at` | *time | 密码验证时间 |
| `totp_verified_at` | *time | TOTP 验证时间 |
| `expires_at` | time | 会话过期时间 |
| `consumed_at` | *time | 会话消费时间 |
| `created_at` | time | 创建时间 |
| `updated_at` | time | 更新时间 |

---

## payment_orders（支付订单表）

记录用户的支付订单信息。

> 注：此表使用**硬删除**，无 `deleted_at` 字段。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `user_id` | int64 | 用户 ID |
| `user_email` | string | 用户邮箱快照 |
| `user_name` | string | 用户名快照 |
| `user_notes` | string | 用户备注快照 |
| `amount` | decimal | 订单金额（USD） |
| `pay_amount` | decimal | 实际支付金额 |
| `fee_rate` | decimal | 手续费率 |
| `recharge_code` | string | 充值码 |
| `out_trade_no` | string | 商户订单号 |
| `payment_type` | string | 支付类型：`alipay` / `wxpay` / `stripe` |
| `payment_trade_no` | string | 支付平台交易号 |
| `pay_url` | *string | 支付链接 |
| `qr_code` | *string | 二维码数据 |
| `qr_code_img` | *string | 二维码图片 |
| `order_type` | string | 订单类型：`balance` / `subscription` |
| `plan_id` | *int64 | 订阅计划 ID |
| `subscription_group_id` | *int64 | 订阅分组 ID |
| `subscription_days` | *int | 订阅天数 |
| `provider_instance_id` | *string | 支付提供商实例 ID |
| `provider_key` | *string | 支付提供商 Key |
| `provider_snapshot` | JSONB | 提供商配置快照 |
| `status` | string | 状态：`PENDING` / `PAID` / `COMPLETED` / `FAILED` / `REFUNDED` |
| `refund_amount` | decimal | 退款金额 |
| `refund_reason` | *string | 退款原因 |
| `refund_at` | *time | 退款时间 |
| `force_refund` | bool | 是否强制退款 |
| `refund_requested_at` | *time | 退款申请时间 |
| `refund_request_reason` | *string | 退款申请原因 |
| `refund_requested_by` | *string | 申请退款人 |
| `expires_at` | time | 订单过期时间 |
| `paid_at` | *time | 支付时间 |
| `completed_at` | *time | 完成时间 |
| `failed_at` | *time | 失败时间 |
| `failed_reason` | *string | 失败原因 |
| `client_ip` | string | 客户端 IP |
| `src_host` | string | 来源 Host |
| `src_url` | *string | 来源 URL |
| `created_at` | time | 创建时间 |
| `updated_at` | time | 更新时间 |

---

## proxies（代理表）

存储 HTTP/SOCKS 代理配置，供 AI 账户调用上游 API 时使用。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `name` | string | 代理名称 |
| `url` | string | 代理 URL |
| `type` | string | 类型（http/socks5 等） |
| `status` | string | 状态 |
| `notes` | string | 备注 |
| `created_at` | time | 创建时间 |
| `updated_at` | time | 更新时间 |
| `deleted_at` | *time | 软删除时间 |

---

## channels（渠道表）

定义模型定价渠道，关联 AI 账户与计费规则。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `name` | string | 渠道名称 |
| `platform` | string | 平台 |
| `pricing_config` | JSONB | 定价配置 |
| `status` | string | 状态 |
| `created_at` | time | 创建时间 |
| `updated_at` | time | 更新时间 |
| `deleted_at` | *time | 软删除时间 |

---

## announcements（公告表）

系统公告，支持向用户展示通知信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `title` | string | 公告标题 |
| `content` | string | 公告内容 |
| `type` | string | 类型 |
| `status` | string | 状态：`active` / `inactive` |
| `starts_at` | *time | 开始展示时间 |
| `ends_at` | *time | 结束展示时间 |
| `created_at` | time | 创建时间 |
| `updated_at` | time | 更新时间 |
| `deleted_at` | *time | 软删除时间 |

---

## redeem_codes（卡密表）

存储可兑换额度的一次性卡密。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `code` | string | 卡密码值（唯一） |
| `amount` | decimal | 可兑换金额（USD） |
| `status` | string | 状态：`unused` / `used` / `expired` |
| `used_by` | *int64 | 使用者用户 ID |
| `used_at` | *time | 使用时间 |
| `expires_at` | *time | 过期时间 |
| `notes` | string | 备注 |
| `created_at` | time | 创建时间 |
| `updated_at` | time | 更新时间 |

---

## promo_codes（优惠码表）

注册或充值时可使用的优惠码。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `code` | string | 优惠码（唯一） |
| `type` | string | 类型（折扣/赠送额度等） |
| `value` | decimal | 优惠值 |
| `max_uses` | int | 最大使用次数（0 = 无限制） |
| `used_count` | int | 已使用次数 |
| `status` | string | 状态 |
| `expires_at` | *time | 过期时间 |
| `created_at` | time | 创建时间 |
| `updated_at` | time | 更新时间 |
| `deleted_at` | *time | 软删除时间 |

---

## user_attributes（用户属性定义表）

管理员自定义的用户扩展属性字段定义。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `name` | string | 属性名 |
| `display_name` | string | 显示名称 |
| `type` | string | 数据类型 |
| `default_value` | string | 默认值 |
| `sort_order` | int | 排序值 |
| `created_at` | time | 创建时间 |
| `updated_at` | time | 更新时间 |
| `deleted_at` | *time | 软删除时间 |

---

## settings（系统设置表）

键值对形式存储全局系统配置（Admin API Key、邮件配置、功能开关等）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int64 | 主键 |
| `key` | string | 配置键（唯一） |
| `value` | string | 配置值 |
| `updated_at` | time | 更新时间 |

---

## 软删除说明

除 `payment_orders` 使用硬删除外，所有主要表均使用 `deleted_at` 软删除。

- 软删除后记录仍保留在数据库中，`deleted_at` 不为 NULL
- 唯一索引通过**部分索引**实现（`WHERE deleted_at IS NULL`），软删除后同名/同邮箱的记录可以重新创建
- ORM 查询默认过滤 `deleted_at IS NULL`

---

## 关系说明

```
users
  ├── api_keys (1:N, user_id)
  ├── auth_identities (1:N, user_id)
  ├── user_subscriptions (1:N, user_id)
  ├── usage_logs (1:N, user_id)
  └── payment_orders (1:N, user_id)

groups
  ├── user_subscriptions (1:N, group_id)
  ├── api_keys (N:1, group_id 可选)
  └── usage_logs (N:1, group_id 可选)

accounts
  ├── proxies (N:1, proxy_id 可选)
  ├── channels (N:1, channel_id 可选)
  └── usage_logs (1:N, account_id)

api_keys
  ├── groups (N:1, group_id 可选)
  └── usage_logs (1:N, api_key_id)
```

# x-api-key 授权接口文档

`x-api-key` 用于**网关调用认证**，覆盖 AI 模型 API 代理端点（Claude、OpenAI、Gemini 等），以及管理员操作端点。

---

## 认证方式

支持以下三种传递方式（任选一种）：

| 方式 | Header | 适用场景 |
|------|--------|---------|
| Bearer 方案 | `Authorization: Bearer {api_key}` | 通用（推荐） |
| x-api-key | `x-api-key: {api_key}` | 管理员操作、兼容多种客户端 |
| x-goog-api-key | `x-goog-api-key: {api_key}` | Gemini CLI 兼容 |

---

## API Key 的两种类型

### 1. 用户 API Key（调用网关）

与特定用户账号关联，用于调用 AI 模型代理接口。

**获取方式：** 登录后通过 JWT 接口管理（见 JWT_AUTH_API.md）

```
POST /api/v1/keys      # 创建
GET  /api/v1/keys      # 列出
```

**Key 的属性：**
- 可设置配额上限（`quota`，USD）
- 可设置过期时间（`expires_at`）
- 可设置 IP 白名单/黑名单
- 可设置时间窗口速率限制（5h / 1d / 7d）
- 可绑定到指定分组（`group_id`）

### 2. Admin API Key（管理操作）

全局单一密钥，不与用户关联，专用于管理员 API 操作。

**获取/管理方式：**（需要管理员登录）
```
GET    /api/v1/admin/settings/admin-api-key             # 查看当前 Key
POST   /api/v1/admin/settings/admin-api-key/regenerate  # 重新生成
DELETE /api/v1/admin/settings/admin-api-key             # 删除
```

**验证机制：** 使用恒时比较（`subtle.ConstantTimeCompare`）防止时序攻击。

---

## 用户 API Key 验证流程

中间件依次执行以下检查：

**第一层：基础鉴权**

| 检查项 | 失败响应 |
|--------|---------|
| 提取 API Key（三种方式之一） | `401 API_KEY_REQUIRED` |
| Key 是否存在 | `401 INVALID_API_KEY` |
| Key 状态（disabled/unknown） | `401 API_KEY_DISABLED` |
| IP 白名单/黑名单 | `403 ACCESS_DENIED` |
| 关联用户是否存在 | `401 USER_NOT_FOUND` |
| 关联用户是否活跃 | `401 USER_INACTIVE` |

**第二层：计费执行**（简单模式下跳过）

| 检查项 | 失败响应 |
|--------|---------|
| Key 配额是否用尽 | `429 API_KEY_QUOTA_EXHAUSTED` |
| Key 是否过期 | `403 API_KEY_EXPIRED` |
| 订阅限额（绑定订阅分组时） | `403 SUBSCRIPTION_NOT_FOUND` / `429 USAGE_LIMIT_EXCEEDED` |
| 用户余额（未绑定订阅时） | `403 INSUFFICIENT_BALANCE` |

---

## 网关接口（用户 API Key）

### Claude API 兼容（`/v1`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/messages` | 发送消息（自动路由 Claude / OpenAI） |
| POST | `/v1/messages/count_tokens` | 计算 Token 数量 |
| GET  | `/v1/models` | 获取可用模型列表 |
| GET  | `/v1/usage` | 获取用量信息 |

### Responses API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/responses` | 创建响应 |
| POST | `/v1/responses/*subpath` | 响应子路径操作 |
| GET  | `/v1/responses` | WebSocket 升级 |

### OpenAI 兼容

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/chat/completions` | Chat Completions |
| POST | `/v1/images/generations` | 图片生成 |
| POST | `/v1/images/edits` | 图片编辑 |

### Gemini 兼容（`/v1beta`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/v1beta/models` | 获取模型列表 |
| GET  | `/v1beta/models/:model` | 获取特定模型信息 |
| POST | `/v1beta/models/*modelAction` | 模型操作（generateContent 等） |

### 别名路由（无 `/v1` 前缀）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/responses` | Responses API 别名 |
| POST | `/responses/*subpath` | 响应子路径别名 |
| GET  | `/responses` | WebSocket 升级别名 |
| POST | `/chat/completions` | Chat Completions 别名 |
| POST | `/images/generations` | 图片生成别名 |
| POST | `/images/edits` | 图片编辑别名 |
| POST | `/backend-api/codex/responses` | Codex 兼容路由 |

### Antigravity 专用路由

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/antigravity/models` | Antigravity 模型列表 |
| POST | `/antigravity/v1/messages` | 消息发送 |
| POST | `/antigravity/v1/messages/count_tokens` | Token 计算 |
| GET  | `/antigravity/v1/models` | 模型列表 |
| GET  | `/antigravity/v1/usage` | 用量信息 |
| GET  | `/antigravity/v1beta/models` | Gemini 兼容模型列表 |
| GET  | `/antigravity/v1beta/models/:model` | 特定模型信息 |
| POST | `/antigravity/v1beta/models/*modelAction` | 模型操作 |

---

## 管理员接口（Admin API Key 或 JWT Admin）

所有 `/api/v1/admin/*` 接口支持以下两种认证之一：
- `x-api-key: {admin_api_key}`
- `Authorization: Bearer {jwt_admin_token}`

### 仪表板

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/dashboard/snapshot-v2` | 快照统计 |
| GET | `/api/v1/admin/dashboard/stats` | 统计数据 |
| GET | `/api/v1/admin/dashboard/realtime` | 实时数据 |
| GET | `/api/v1/admin/dashboard/trend` | 趋势数据 |
| GET | `/api/v1/admin/dashboard/models` | 模型统计 |
| GET | `/api/v1/admin/dashboard/groups` | 分组统计 |
| GET | `/api/v1/admin/dashboard/api-keys-trend` | API Key 趋势 |
| GET | `/api/v1/admin/dashboard/users-trend` | 用户趋势 |
| GET | `/api/v1/admin/dashboard/users-ranking` | 用户排行 |
| POST | `/api/v1/admin/dashboard/users-usage` | 用户用量统计 |
| POST | `/api/v1/admin/dashboard/api-keys-usage` | API Key 用量统计 |
| GET | `/api/v1/admin/dashboard/user-breakdown` | 用户拆分统计 |
| POST | `/api/v1/admin/dashboard/aggregation/backfill` | 聚合数据补填 |

### 用户管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET    | `/api/v1/admin/users` | 用户列表 |
| GET    | `/api/v1/admin/users/:id` | 用户详情 |
| POST   | `/api/v1/admin/users` | 创建用户 |
| PUT    | `/api/v1/admin/users/:id` | 更新用户 |
| DELETE | `/api/v1/admin/users/:id` | 删除用户 |
| POST   | `/api/v1/admin/users/:id/auth-identities` | 添加认证身份 |
| POST   | `/api/v1/admin/users/:id/balance` | 调整用户余额 |
| GET    | `/api/v1/admin/users/:id/api-keys` | 用户的 API Key 列表 |
| GET    | `/api/v1/admin/users/:id/usage` | 用户使用记录 |
| GET    | `/api/v1/admin/users/:id/balance-history` | 余额变更历史 |
| POST   | `/api/v1/admin/users/:id/replace-group` | 替换用户分组 |
| GET    | `/api/v1/admin/users/:id/rpm-status` | RPM 限速状态 |
| GET    | `/api/v1/admin/users/:id/attributes` | 用户属性 |
| PUT    | `/api/v1/admin/users/:id/attributes` | 更新用户属性 |

### 分组管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET    | `/api/v1/admin/groups` | 分组列表（分页） |
| GET    | `/api/v1/admin/groups/all` | 所有分组 |
| GET    | `/api/v1/admin/groups/usage-summary` | 用量汇总 |
| GET    | `/api/v1/admin/groups/capacity-summary` | 容量汇总 |
| PUT    | `/api/v1/admin/groups/sort-order` | 更新排序 |
| GET    | `/api/v1/admin/groups/:id` | 分组详情 |
| POST   | `/api/v1/admin/groups` | 创建分组 |
| PUT    | `/api/v1/admin/groups/:id` | 更新分组 |
| DELETE | `/api/v1/admin/groups/:id` | 删除分组 |
| GET    | `/api/v1/admin/groups/:id/stats` | 分组统计 |
| GET    | `/api/v1/admin/groups/:id/rate-multipliers` | 获取费率倍率 |
| PUT    | `/api/v1/admin/groups/:id/rate-multipliers` | 更新费率倍率 |
| DELETE | `/api/v1/admin/groups/:id/rate-multipliers` | 删除费率倍率 |
| PUT    | `/api/v1/admin/groups/:id/rpm-overrides` | 更新 RPM 覆盖 |
| DELETE | `/api/v1/admin/groups/:id/rpm-overrides` | 删除 RPM 覆盖 |
| GET    | `/api/v1/admin/groups/:id/api-keys` | 分组下 API Key |
| GET    | `/api/v1/admin/groups/:id/subscriptions` | 分组订阅列表 |

### AI 账户管理（accounts）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET    | `/api/v1/admin/accounts` | 账户列表 |
| GET    | `/api/v1/admin/accounts/:id` | 账户详情 |
| POST   | `/api/v1/admin/accounts` | 创建账户 |
| PUT    | `/api/v1/admin/accounts/:id` | 更新账户 |
| DELETE | `/api/v1/admin/accounts/:id` | 删除账户 |
| POST   | `/api/v1/admin/accounts/:id/test` | 测试账户可用性 |
| POST   | `/api/v1/admin/accounts/:id/recover-state` | 恢复账户状态 |
| POST   | `/api/v1/admin/accounts/:id/refresh` | 刷新账户 |
| POST   | `/api/v1/admin/accounts/:id/set-privacy` | 设置隐私模式 |
| POST   | `/api/v1/admin/accounts/:id/refresh-tier` | 刷新账户 Tier |
| GET    | `/api/v1/admin/accounts/:id/stats` | 账户统计 |
| POST   | `/api/v1/admin/accounts/:id/clear-error` | 清除错误状态 |
| GET    | `/api/v1/admin/accounts/:id/usage` | 账户使用记录 |
| GET    | `/api/v1/admin/accounts/:id/today-stats` | 今日统计 |
| POST   | `/api/v1/admin/accounts/today-stats/batch` | 批量今日统计 |
| POST   | `/api/v1/admin/accounts/:id/clear-rate-limit` | 清除限速 |
| POST   | `/api/v1/admin/accounts/:id/reset-quota` | 重置配额 |
| GET    | `/api/v1/admin/accounts/:id/temp-unschedulable` | 获取临时不可调度状态 |
| DELETE | `/api/v1/admin/accounts/:id/temp-unschedulable` | 清除临时不可调度 |
| POST   | `/api/v1/admin/accounts/:id/schedulable` | 设置为可调度 |
| GET    | `/api/v1/admin/accounts/:id/models` | 账户支持模型 |
| POST   | `/api/v1/admin/accounts/batch` | 批量创建 |
| GET    | `/api/v1/admin/accounts/data` | 导出数据 |
| POST   | `/api/v1/admin/accounts/data` | 导入数据 |
| POST   | `/api/v1/admin/accounts/batch-update-credentials` | 批量更新凭证 |
| POST   | `/api/v1/admin/accounts/batch-refresh-tier` | 批量刷新 Tier |
| POST   | `/api/v1/admin/accounts/bulk-update` | 批量更新 |
| POST   | `/api/v1/admin/accounts/batch-clear-error` | 批量清除错误 |
| POST   | `/api/v1/admin/accounts/batch-refresh` | 批量刷新 |
| POST   | `/api/v1/admin/accounts/check-mixed-channel` | 检查混合渠道 |
| POST   | `/api/v1/admin/accounts/sync/crs` | 同步 CRS |
| POST   | `/api/v1/admin/accounts/sync/crs/preview` | 预览 CRS 同步 |
| GET    | `/api/v1/admin/accounts/antigravity/default-model-mapping` | Antigravity 默认模型映射 |

### OAuth 账户授权

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/admin/accounts/generate-auth-url` | 生成 Claude OAuth URL |
| POST | `/api/v1/admin/accounts/generate-setup-token-url` | 生成 Setup Token URL |
| POST | `/api/v1/admin/accounts/exchange-code` | 交换授权码 |
| POST | `/api/v1/admin/accounts/exchange-setup-token-code` | 交换 Setup Token |
| POST | `/api/v1/admin/accounts/cookie-auth` | Cookie 认证 |
| POST | `/api/v1/admin/openai/generate-auth-url` | OpenAI OAuth URL |
| POST | `/api/v1/admin/openai/exchange-code` | OpenAI 交换授权码 |
| POST | `/api/v1/admin/openai/refresh-token` | OpenAI 刷新 Token |
| POST | `/api/v1/admin/openai/create-from-oauth` | 从 OAuth 创建账户 |
| POST | `/api/v1/admin/gemini/oauth/auth-url` | Gemini OAuth URL |
| POST | `/api/v1/admin/gemini/oauth/exchange-code` | Gemini 交换授权码 |
| GET  | `/api/v1/admin/gemini/oauth/capabilities` | Gemini 能力查询 |
| POST | `/api/v1/admin/antigravity/oauth/auth-url` | Antigravity OAuth URL |
| POST | `/api/v1/admin/antigravity/oauth/exchange-code` | Antigravity 交换授权码 |
| POST | `/api/v1/admin/antigravity/oauth/refresh-token` | Antigravity 刷新 Token |

### 代理管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET    | `/api/v1/admin/proxies` | 代理列表 |
| GET    | `/api/v1/admin/proxies/all` | 所有代理 |
| GET    | `/api/v1/admin/proxies/data` | 导出数据 |
| POST   | `/api/v1/admin/proxies/data` | 导入数据 |
| GET    | `/api/v1/admin/proxies/:id` | 代理详情 |
| POST   | `/api/v1/admin/proxies` | 创建代理 |
| PUT    | `/api/v1/admin/proxies/:id` | 更新代理 |
| DELETE | `/api/v1/admin/proxies/:id` | 删除代理 |
| POST   | `/api/v1/admin/proxies/:id/test` | 测试代理 |
| POST   | `/api/v1/admin/proxies/:id/quality-check` | 代理质量检查 |
| GET    | `/api/v1/admin/proxies/:id/stats` | 代理统计 |
| GET    | `/api/v1/admin/proxies/:id/accounts` | 代理关联账户 |
| POST   | `/api/v1/admin/proxies/batch-delete` | 批量删除 |
| POST   | `/api/v1/admin/proxies/batch` | 批量创建 |

### 渠道管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET    | `/api/v1/admin/channels` | 渠道列表 |
| GET    | `/api/v1/admin/channels/model-pricing` | 模型定价 |
| GET    | `/api/v1/admin/channels/:id` | 渠道详情 |
| POST   | `/api/v1/admin/channels` | 创建渠道 |
| PUT    | `/api/v1/admin/channels/:id` | 更新渠道 |
| DELETE | `/api/v1/admin/channels/:id` | 删除渠道 |

### 渠道监控

| 方法 | 路径 | 说明 |
|------|------|------|
| GET    | `/api/v1/admin/channel-monitors` | 监控列表 |
| POST   | `/api/v1/admin/channel-monitors` | 创建监控 |
| GET    | `/api/v1/admin/channel-monitors/:id` | 监控详情 |
| PUT    | `/api/v1/admin/channel-monitors/:id` | 更新监控 |
| DELETE | `/api/v1/admin/channel-monitors/:id` | 删除监控 |
| POST   | `/api/v1/admin/channel-monitors/:id/run` | 手动执行 |
| GET    | `/api/v1/admin/channel-monitors/:id/history` | 执行历史 |
| GET    | `/api/v1/admin/channel-monitor-templates` | 模板列表 |
| POST   | `/api/v1/admin/channel-monitor-templates` | 创建模板 |
| GET    | `/api/v1/admin/channel-monitor-templates/:id` | 模板详情 |
| PUT    | `/api/v1/admin/channel-monitor-templates/:id` | 更新模板 |
| DELETE | `/api/v1/admin/channel-monitor-templates/:id` | 删除模板 |
| GET    | `/api/v1/admin/channel-monitor-templates/:id/monitors` | 模板关联监控 |
| POST   | `/api/v1/admin/channel-monitor-templates/:id/apply` | 应用模板 |

### 公告管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET    | `/api/v1/admin/announcements` | 公告列表 |
| POST   | `/api/v1/admin/announcements` | 创建公告 |
| GET    | `/api/v1/admin/announcements/:id` | 公告详情 |
| PUT    | `/api/v1/admin/announcements/:id` | 更新公告 |
| DELETE | `/api/v1/admin/announcements/:id` | 删除公告 |
| GET    | `/api/v1/admin/announcements/:id/read-status` | 阅读状态 |

### 卡密管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET    | `/api/v1/admin/redeem-codes` | 卡密列表 |
| GET    | `/api/v1/admin/redeem-codes/stats` | 卡密统计 |
| GET    | `/api/v1/admin/redeem-codes/export` | 导出卡密 |
| GET    | `/api/v1/admin/redeem-codes/:id` | 卡密详情 |
| POST   | `/api/v1/admin/redeem-codes/create-and-redeem` | 创建并立即兑换 |
| POST   | `/api/v1/admin/redeem-codes/generate` | 批量生成卡密 |
| DELETE | `/api/v1/admin/redeem-codes/:id` | 删除卡密 |
| POST   | `/api/v1/admin/redeem-codes/batch-delete` | 批量删除 |
| POST   | `/api/v1/admin/redeem-codes/:id/expire` | 使卡密过期 |

### 优惠码管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET    | `/api/v1/admin/promo-codes` | 优惠码列表 |
| GET    | `/api/v1/admin/promo-codes/:id` | 优惠码详情 |
| POST   | `/api/v1/admin/promo-codes` | 创建优惠码 |
| PUT    | `/api/v1/admin/promo-codes/:id` | 更新优惠码 |
| DELETE | `/api/v1/admin/promo-codes/:id` | 删除优惠码 |
| GET    | `/api/v1/admin/promo-codes/:id/usages` | 使用记录 |

### 订阅管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/admin/subscriptions` | 订阅列表 |
| GET  | `/api/v1/admin/subscriptions/:id` | 订阅详情 |
| GET  | `/api/v1/admin/subscriptions/:id/progress` | 订阅进度 |
| POST | `/api/v1/admin/subscriptions/assign` | 分配订阅 |
| POST | `/api/v1/admin/subscriptions/bulk-assign` | 批量分配 |
| POST | `/api/v1/admin/subscriptions/:id/extend` | 延长订阅 |
| POST | `/api/v1/admin/subscriptions/:id/reset-quota` | 重置配额 |
| DELETE | `/api/v1/admin/subscriptions/:id` | 删除订阅 |
| GET  | `/api/v1/admin/users/:id/subscriptions` | 用户订阅列表 |

### 使用记录管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/admin/usage` | 全局使用记录 |
| GET  | `/api/v1/admin/usage/stats` | 全局统计 |
| GET  | `/api/v1/admin/usage/search-users` | 按用户搜索 |
| GET  | `/api/v1/admin/usage/search-api-keys` | 按 API Key 搜索 |
| GET  | `/api/v1/admin/usage/cleanup-tasks` | 清理任务列表 |
| POST | `/api/v1/admin/usage/cleanup-tasks` | 创建清理任务 |
| POST | `/api/v1/admin/usage/cleanup-tasks/:id/cancel` | 取消清理任务 |

### 系统设置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/admin/settings` | 获取系统设置 |
| PUT  | `/api/v1/admin/settings` | 更新系统设置 |
| POST | `/api/v1/admin/settings/test-smtp` | 测试 SMTP |
| POST | `/api/v1/admin/settings/send-test-email` | 发送测试邮件 |
| GET  | `/api/v1/admin/settings/admin-api-key` | 获取 Admin API Key |
| POST | `/api/v1/admin/settings/admin-api-key/regenerate` | 重新生成 Admin Key |
| DELETE | `/api/v1/admin/settings/admin-api-key` | 删除 Admin Key |
| GET  | `/api/v1/admin/settings/overload-cooldown` | 过载冷却配置 |
| PUT  | `/api/v1/admin/settings/overload-cooldown` | 更新过载冷却 |
| GET  | `/api/v1/admin/settings/stream-timeout` | 流式超时配置 |
| PUT  | `/api/v1/admin/settings/stream-timeout` | 更新流式超时 |
| GET  | `/api/v1/admin/settings/rectifier` | 修正器配置 |
| PUT  | `/api/v1/admin/settings/rectifier` | 更新修正器 |
| GET  | `/api/v1/admin/settings/beta-policy` | Beta 策略 |
| PUT  | `/api/v1/admin/settings/beta-policy` | 更新 Beta 策略 |
| GET  | `/api/v1/admin/settings/web-search-emulation` | 网页搜索仿真配置 |
| PUT  | `/api/v1/admin/settings/web-search-emulation` | 更新网页搜索仿真 |
| POST | `/api/v1/admin/settings/web-search-emulation/test` | 测试网页搜索仿真 |
| POST | `/api/v1/admin/settings/web-search-emulation/reset-usage` | 重置搜索用量 |

### 系统管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/admin/system/version` | 当前版本 |
| GET  | `/api/v1/admin/system/check-updates` | 检查更新 |
| POST | `/api/v1/admin/system/update` | 执行更新 |
| POST | `/api/v1/admin/system/rollback` | 回滚版本 |
| POST | `/api/v1/admin/system/restart` | 重启服务 |

### 运维监控（Ops）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/admin/ops/concurrency` | 并发状态 |
| GET  | `/api/v1/admin/ops/user-concurrency` | 用户并发状态 |
| GET  | `/api/v1/admin/ops/account-availability` | 账户可用性 |
| GET  | `/api/v1/admin/ops/realtime-traffic` | 实时流量 |
| GET  | `/api/v1/admin/ops/alert-rules` | 告警规则列表 |
| POST | `/api/v1/admin/ops/alert-rules` | 创建告警规则 |
| PUT  | `/api/v1/admin/ops/alert-rules/:id` | 更新告警规则 |
| DELETE | `/api/v1/admin/ops/alert-rules/:id` | 删除告警规则 |
| GET  | `/api/v1/admin/ops/alert-events` | 告警事件列表 |
| GET  | `/api/v1/admin/ops/alert-events/:id` | 告警事件详情 |
| PUT  | `/api/v1/admin/ops/alert-events/:id/status` | 更新告警状态 |
| POST | `/api/v1/admin/ops/alert-silences` | 创建告警静默 |
| GET  | `/api/v1/admin/ops/errors` | 错误列表 |
| GET  | `/api/v1/admin/ops/errors/:id` | 错误详情 |
| GET  | `/api/v1/admin/ops/errors/:id/retries` | 重试记录 |
| POST | `/api/v1/admin/ops/errors/:id/retry` | 手动重试 |
| PUT  | `/api/v1/admin/ops/errors/:id/resolve` | 标记已解决 |
| GET  | `/api/v1/admin/ops/request-errors` | 请求错误列表 |
| GET  | `/api/v1/admin/ops/upstream-errors` | 上游错误列表 |
| GET  | `/api/v1/admin/ops/requests` | 请求详情列表 |
| GET  | `/api/v1/admin/ops/system-logs` | 系统日志 |
| POST | `/api/v1/admin/ops/system-logs/cleanup` | 清理日志 |
| GET  | `/api/v1/admin/ops/dashboard/snapshot-v2` | Ops 仪表板快照 |
| GET  | `/api/v1/admin/ops/dashboard/overview` | 概览统计 |
| GET  | `/api/v1/admin/ops/ws/qps` | WebSocket 实时 QPS |

### API Key 管理（管理员）

| 方法 | 路径 | 说明 |
|------|------|------|
| PUT | `/api/v1/admin/api-keys/:id` | 更新任意用户的 API Key |

### 用户属性

| 方法 | 路径 | 说明 |
|------|------|------|
| GET    | `/api/v1/admin/user-attributes` | 属性定义列表 |
| POST   | `/api/v1/admin/user-attributes` | 创建属性定义 |
| POST   | `/api/v1/admin/user-attributes/batch` | 批量创建 |
| PUT    | `/api/v1/admin/user-attributes/reorder` | 重新排序 |
| PUT    | `/api/v1/admin/user-attributes/:id` | 更新属性定义 |
| DELETE | `/api/v1/admin/user-attributes/:id` | 删除属性定义 |

### 邀请返利

| 方法 | 路径 | 说明 |
|------|------|------|
| GET    | `/api/v1/admin/affiliates/users` | 返利用户列表 |
| GET    | `/api/v1/admin/affiliates/users/lookup` | 查询返利用户 |
| POST   | `/api/v1/admin/affiliates/users/batch-rate` | 批量设置返利率 |
| PUT    | `/api/v1/admin/affiliates/users/:user_id` | 更新返利用户 |
| DELETE | `/api/v1/admin/affiliates/users/:user_id` | 删除返利用户 |

### 支付管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/admin/payment/dashboard` | 支付仪表板 |
| GET  | `/api/v1/admin/payment/config` | 支付配置 |
| PUT  | `/api/v1/admin/payment/config` | 更新支付配置 |
| GET  | `/api/v1/admin/payment/orders` | 订单列表 |
| GET  | `/api/v1/admin/payment/orders/:id` | 订单详情 |
| POST | `/api/v1/admin/payment/orders/:id/cancel` | 取消订单 |
| POST | `/api/v1/admin/payment/orders/:id/retry` | 重试履行 |
| POST | `/api/v1/admin/payment/orders/:id/refund` | 处理退款 |
| GET  | `/api/v1/admin/payment/plans` | 订阅计划列表 |
| POST | `/api/v1/admin/payment/plans` | 创建订阅计划 |
| PUT  | `/api/v1/admin/payment/plans/:id` | 更新订阅计划 |
| DELETE | `/api/v1/admin/payment/plans/:id` | 删除订阅计划 |
| GET  | `/api/v1/admin/payment/providers` | 支付提供商列表 |
| POST | `/api/v1/admin/payment/providers` | 创建支付提供商 |
| PUT  | `/api/v1/admin/payment/providers/:id` | 更新支付提供商 |
| DELETE | `/api/v1/admin/payment/providers/:id` | 删除支付提供商 |

### 数据管理 & 备份

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/admin/data-management/agent/health` | Agent 健康检查 |
| GET  | `/api/v1/admin/data-management/config` | 数据管理配置 |
| PUT  | `/api/v1/admin/data-management/config` | 更新配置 |
| POST | `/api/v1/admin/backups` | 创建备份 |
| GET  | `/api/v1/admin/backups` | 备份列表 |
| GET  | `/api/v1/admin/backups/:id` | 备份详情 |
| DELETE | `/api/v1/admin/backups/:id` | 删除备份 |
| GET  | `/api/v1/admin/backups/:id/download-url` | 获取下载 URL |
| POST | `/api/v1/admin/backups/:id/restore` | 从备份恢复 |

### 定时测试计划

| 方法 | 路径 | 说明 |
|------|------|------|
| POST   | `/api/v1/admin/scheduled-test-plans` | 创建测试计划 |
| PUT    | `/api/v1/admin/scheduled-test-plans/:id` | 更新测试计划 |
| DELETE | `/api/v1/admin/scheduled-test-plans/:id` | 删除测试计划 |
| GET    | `/api/v1/admin/scheduled-test-plans/:id/results` | 执行结果 |
| GET    | `/api/v1/admin/accounts/:id/scheduled-test-plans` | 账户的测试计划 |

### 其他管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET    | `/api/v1/admin/error-passthrough-rules` | 错误透传规则列表 |
| POST   | `/api/v1/admin/error-passthrough-rules` | 创建规则 |
| PUT    | `/api/v1/admin/error-passthrough-rules/:id` | 更新规则 |
| DELETE | `/api/v1/admin/error-passthrough-rules/:id` | 删除规则 |
| GET    | `/api/v1/admin/tls-fingerprint-profiles` | TLS 指纹模板列表 |
| POST   | `/api/v1/admin/tls-fingerprint-profiles` | 创建模板 |
| PUT    | `/api/v1/admin/tls-fingerprint-profiles/:id` | 更新模板 |
| DELETE | `/api/v1/admin/tls-fingerprint-profiles/:id` | 删除模板 |

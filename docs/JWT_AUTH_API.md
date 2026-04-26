# JWT 授权接口文档

JWT 用于**用户身份认证**，覆盖用户个人资料、API Key 管理、使用记录等端点。

---

## 认证方式

所有需要 JWT 的接口均在请求头中携带：

```
Authorization: Bearer {access_token}
```

---

## 获取 Token

### 账号密码登录

```
POST /api/v1/auth/login
```

**请求体：**
```json
{
  "email": "user@example.com",
  "password": "your_password"
}
```

**响应：**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "...",
  "expires_in": 3600
}
```

### 双因素认证登录

```
POST /api/v1/auth/login/2fa
```

若账号开启了 TOTP，在 `/auth/login` 返回要求 2FA 后，继续调用此接口。

### 刷新 Token

```
POST /api/v1/auth/refresh
```

**请求体：**
```json
{
  "refresh_token": "..."
}
```

### OAuth 登录（LinuxDo / WeChat / OIDC）

1. `GET /api/v1/auth/oauth/{provider}/start` — 获取授权跳转 URL
2. 用户完成授权后回调 `GET /api/v1/auth/oauth/{provider}/callback`
3. `POST /api/v1/auth/oauth/{provider}/bind-login` — 完成登录获取 Token

`{provider}` 可为 `linuxdo`、`wechat`、`oidc`。

---

## Token 验证机制

中间件依次执行以下检查（任意一项失败返回对应错误）：

| 检查项 | 失败响应 |
|--------|---------|
| 提取 Bearer Token | `401 TOKEN_REQUIRED` |
| 签名 & 有效期验证 | `401 INVALID_TOKEN` |
| Token 是否过期 | `401 TOKEN_EXPIRED` |
| 用户是否存在 | `401 USER_NOT_FOUND` |
| 用户状态是否活跃 | `401 USER_INACTIVE` |
| TokenVersion 版本匹配 | `401 TOKEN_REVOKED`（密码修改后旧 Token 立即失效）|

---

## 公开接口（无需 JWT）

以下接口无需任何认证：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册 |
| POST | `/api/v1/auth/login` | 登录 |
| POST | `/api/v1/auth/refresh` | 刷新 Token |
| POST | `/api/v1/auth/logout` | 登出 |
| POST | `/api/v1/auth/forgot-password` | 忘记密码 |
| POST | `/api/v1/auth/reset-password` | 重置密码 |
| POST | `/api/v1/auth/send-verify-code` | 发送验证码 |
| POST | `/api/v1/auth/validate-promo-code` | 验证优惠码 |
| POST | `/api/v1/auth/validate-invitation-code` | 验证邀请码 |
| GET  | `/api/v1/settings/public` | 获取公开设置 |
| GET  | `/setup/status` | 获取初始化状态 |
| GET  | `/health` | 健康检查 |

---

## 需要 JWT 的接口

### 认证相关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/auth/me` | 获取当前登录用户信息 |
| POST | `/api/v1/auth/revoke-all-sessions` | 撤销所有会话（强制下线所有设备） |
| POST | `/api/v1/auth/oauth/bind-token` | 准备 OAuth 绑定令牌 |

### 用户资料

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/user/profile` | 获取用户档案 |
| PUT  | `/api/v1/user` | 更新用户档案 |
| PUT  | `/api/v1/user/password` | 修改密码 |
| GET  | `/api/v1/user/aff` | 获取邀请返利信息 |
| POST | `/api/v1/user/aff/transfer` | 转移返利额度 |

### 账号绑定

| 方法 | 路径 | 说明 |
|------|------|------|
| POST   | `/api/v1/user/account-bindings/email/send-code` | 发送邮箱绑定验证码 |
| POST   | `/api/v1/user/account-bindings/email` | 绑定邮箱身份 |
| DELETE | `/api/v1/user/account-bindings/:provider` | 解绑第三方身份 |
| POST   | `/api/v1/user/auth-identities/bind/start` | 开始身份绑定流程 |

### 通知邮箱

| 方法 | 路径 | 说明 |
|------|------|------|
| POST   | `/api/v1/user/notify-email/send-code` | 发送通知邮箱验证码 |
| POST   | `/api/v1/user/notify-email/verify` | 验证通知邮箱 |
| PUT    | `/api/v1/user/notify-email/toggle` | 开启/关闭邮件通知 |
| DELETE | `/api/v1/user/notify-email` | 移除通知邮箱 |

### TOTP 双因素认证

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/user/totp/status` | 获取 TOTP 启用状态 |
| GET  | `/api/v1/user/totp/verification-method` | 获取验证方式 |
| POST | `/api/v1/user/totp/send-code` | 发送验证码 |
| POST | `/api/v1/user/totp/setup` | 初始化 TOTP 设置（获取二维码） |
| POST | `/api/v1/user/totp/enable` | 确认启用 TOTP |
| POST | `/api/v1/user/totp/disable` | 禁用 TOTP |

### API Key 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET    | `/api/v1/keys` | 获取 API Key 列表 |
| GET    | `/api/v1/keys/:id` | 获取特定 API Key 详情 |
| POST   | `/api/v1/keys` | 创建 API Key |
| PUT    | `/api/v1/keys/:id` | 更新 API Key（名称、配额、过期时间等） |
| DELETE | `/api/v1/keys/:id` | 删除 API Key |

### 分组与渠道

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/groups/available` | 获取可用分组列表 |
| GET | `/api/v1/groups/rates` | 获取分组计费费率 |
| GET | `/api/v1/channels/available` | 获取可用渠道列表 |

### 使用记录

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/usage` | 获取使用记录列表 |
| GET  | `/api/v1/usage/:id` | 获取特定使用记录详情 |
| GET  | `/api/v1/usage/stats` | 获取使用统计汇总 |
| GET  | `/api/v1/usage/dashboard/stats` | 仪表板统计数据 |
| GET  | `/api/v1/usage/dashboard/trend` | 使用趋势（按时间） |
| GET  | `/api/v1/usage/dashboard/models` | 模型使用分布统计 |
| POST | `/api/v1/usage/dashboard/api-keys-usage` | API Key 使用统计 |

### 公告

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/announcements` | 获取公告列表 |
| POST | `/api/v1/announcements/:id/read` | 标记公告为已读 |

### 卡密兑换

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/redeem` | 兑换卡密 |
| GET  | `/api/v1/redeem/history` | 查看兑换历史 |

### 订阅

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/subscriptions` | 获取我的订阅列表 |
| GET | `/api/v1/subscriptions/active` | 获取当前活跃订阅 |
| GET | `/api/v1/subscriptions/progress` | 获取订阅用量进度 |
| GET | `/api/v1/subscriptions/summary` | 获取订阅汇总信息 |

### 渠道监控

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/channel-monitors` | 获取渠道监控列表 |
| GET | `/api/v1/channel-monitors/:id/status` | 获取监控状态 |

### 支付（用户端）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/v1/payment/config` | 获取支付配置 |
| GET  | `/api/v1/payment/checkout-info` | 获取结账信息 |
| GET  | `/api/v1/payment/plans` | 获取订阅计划列表 |
| GET  | `/api/v1/payment/channels` | 获取支付渠道列表 |
| GET  | `/api/v1/payment/limits` | 获取支付限额 |
| POST | `/api/v1/payment/orders` | 创建支付订单 |
| POST | `/api/v1/payment/orders/verify` | 验证订单状态 |
| GET  | `/api/v1/payment/orders/my` | 获取我的订单列表 |
| GET  | `/api/v1/payment/orders/:id` | 获取订单详情 |
| POST | `/api/v1/payment/orders/:id/cancel` | 取消订单 |
| POST | `/api/v1/payment/orders/:id/refund-request` | 申请退款 |
| GET  | `/api/v1/payment/orders/refund-eligible-providers` | 获取支持退款的支付提供商 |

---

## 管理员接口（需要 JWT Admin 角色）

管理员 JWT 与普通用户 JWT 获取方式相同（登录时 role 为 `admin`），可访问所有 `/api/v1/admin/*` 接口。Admin 接口同时也支持 `x-api-key` 认证（见 X_API_KEY_AUTH_API.md）。

WebSocket 升级请求（无法设置标准 HTTP 头）可通过以下方式传递 JWT：

```
Sec-WebSocket-Protocol: sub2api-admin, jwt.{access_token}
```

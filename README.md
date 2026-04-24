# G7E6 AI Studio

G7E6 AI Studio 是部署在 `G7e6ai.com/app/ai` 下的 sub2api 扩展站点。当前 MVP 提供 `gpt-image-2` 文生图页面，并复用 sub2api 的登录状态。

## 技术栈

- 前端：Vue 3 + Vite + TypeScript
- 后端：Python + FastAPI + httpx
- 鉴权：前端读取 sub2api 同域 `localStorage.auth_token`，后端调用 sub2api `/api/v1/auth/me` 校验
- 图片接口：`https://g7e6ai.com/v1/images/generations`

## 环境变量

复制示例配置：

```bash
cp .env.example .env
```

至少配置：

```bash
IMAGE_API_KEY=sk-xxx
SUB2API_BASE_URL=https://g7e6ai.com/api/v1
IMAGE_API_URL=https://g7e6ai.com/v1/images/generations
```


## 本地开发登录

本地开发环境和 `G7e6ai.com` 不是同一个 origin，浏览器不会共享线上站点的 `localStorage`。开发时可以手动复制线上 token：

1. 在 `https://G7e6ai.com` 登录。
2. 打开浏览器控制台执行：

```js
localStorage.getItem('auth_token')
```

3. 复制返回的 token。
4. 打开本地 `http://127.0.0.1:5173/app/ai/images`。
5. 页面顶部会出现“开发登录”面板，粘贴 token 并保存。

保存后，本地前端会把 token 放到 `Authorization` 请求头；本地 FastAPI 后端会调用 `SUB2API_BASE_URL/auth/me` 校验登录状态。

## 启动后端

```bash
cd ~/workspace/tool/ai-studio
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 18081 --reload
```

## 启动前端

```bash
cd ~/workspace/tool/ai-studio
npm install
npm run dev
```

开发访问：

```text
http://127.0.0.1:5173/app/ai/images
```

## 生产部署

构建前端：

```bash
npm run build
```

Nginx 示例：

```nginx
location /app/ai/ {
  alias /var/www/g7e6-ai-studio/dist/;
  try_files $uri $uri/ /app/ai/index.html;
}

location /app/ai-api/ {
  proxy_pass http://127.0.0.1:18081/;
  proxy_set_header Host $host;
  proxy_set_header Authorization $http_authorization;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

## 当前功能

- 输入最多 5000 字提示词
- 选择宽高比：`1:1`、`16:9`、`9:16`、`4:3`、`3:4`
- 选择尺寸：`1K`、`2K`
- 使用模型：`gpt-image-2`
- 返回 base64 图片并支持下载

参考图片上传 UI 已预留；当前后端仍按文生图接口发送 prompt，暂未调用多图参考接口。


## 参考图说明

- 不上传参考图时，前端调用 `POST /app/ai-api/images/generations`，后端转发到 `IMAGE_API_URL`。
- 上传 1-3 张参考图时，前端调用 `POST /app/ai-api/images/edits`，后端用 multipart/form-data 转发到 `IMAGE_EDIT_API_URL`。
- 默认图片字段名是 `image[]`；如果上游网关不兼容，后端会自动 fallback 为重复的 `image` 字段。
- 支持 `JPEG`、`PNG`、`WebP`，单张最大 5MB。

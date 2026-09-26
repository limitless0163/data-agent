# frontend

TypeScript + React 19 + Next.js 16（App Router）实现的单页聊天界面。用户在输入框中提交自然语言问题，前端通过 `POST /api/query`（Next.js Route Handler，SSE 转发）拿到后端 LangGraph Agent 的流式事件，将每个步骤状态实时显示为气泡，最终结果以表格形式渲染。

| 关注点 | 技术 |
| --- | --- |
| 框架 | Next.js 16（App Router） |
| UI 库 | React 19.3 |
| 语言 | TypeScript 5.9（`strict`、`noEmit`、`moduleResolution: "bundler"`） |
| 运行时 | Node 22（Dockerfile 与 `Dockerfile.dev` 均一致） |
| 样式 | 原生 CSS + `:root` CSS 变量（`src/styles/style.css`，仅亮色主题） |
| 状态管理 | 仅 React Hooks（`useState` + `useRef`） |
| 路径别名 | 无；统一使用相对路径 |

## 先决条件

- Node 22（`Dockerfile` 与 `Dockerfile.dev` 基镜像：`node:22-alpine`）
- npm（仓库提交了 `package-lock.json`，使用 `npm ci`）
- 后端 API 在本地 `http://localhost:8000` 运行，或通过 `API_BASE_URL` 指向远程后端

> 推荐直接使用根目录的 `make dev` 启动完整栈；只有需要独立调试前端时才用下面的原生命令。

## 安装

```bash
cd frontend
npm ci
```

## 命令

| 目标 | 命令 |
| --- | --- |
| 启动开发服务器（HMR） | `npm run dev` → http://localhost:3000 |
| 生产构建 | `npm run build` |
| 启动生产服务器 | `npm run start` |
| 类型检查 | `npm run typecheck`（`tsc --noEmit`） |

仓库根目录的快捷方式：

| 命令 | 说明 |
| --- | --- |
| `make dev` / `make up` | 通过 Compose 启动开发栈，前端容器挂载源码 + 启用 `WATCHPACK_POLLING` |
| `make typecheck` | `exec` 进前端容器执行 `npm run typecheck` |
| `make logs SERVICE=frontend` | 查看前端日志 |
| `make smoke` | HTTP 探活（`/`、`/api/query` 校验） |

## 路由

| 路径 | 文件 | 说明 |
| --- | --- | --- |
| `/` | `src/app/page.tsx` | 渲染 `<ChatPage />`，整个聊天界面 |
| `/api/query` | `src/app/api/query/route.ts` | `POST` → SSE 转发到 `${API_BASE_URL ?? "http://localhost:8000"}/api/query`；运行时 `nodejs` |

`/api/query` 路由仅做 SSE 透传：

- 透传上游 `response.body`（保持 chunked 编码），不要 buffer；
- 透传 `Content-Type`（默认 `text/event-stream; charset=utf-8`）；
- 设置 `Cache-Control: no-cache, no-transform`；
- 透传 `signal: request.signal`，客户端断开即中止上游；
- 网络异常返回 `502 { "message": "后端服务不可用" }`。

## 环境变量

| 变量 | 作用范围 | 默认 | 说明 |
| --- | --- | --- | --- |
| `API_BASE_URL` | 服务端（路由处理器内） | `http://localhost:8000` | 转发到后端的基础 URL。Compose 中设为 `http://backend:8000` |
| `NODE_ENV` | 服务端 | — | dev Compose 设为 `development` |
| `WATCHPACK_POLLING` | dev Compose | `"true"` | 启用 Webpack 文件轮询，便于在挂载卷上做 HMR |

目前没有使用 `NEXT_PUBLIC_*` 变量，因此不会暴露到客户端 bundle。

## 源码结构

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx                # <html lang="zh-CN"> + 全局样式；metadata.title = "掌柜问数"
│   │   ├── page.tsx                  # 渲染 <ChatPage />（服务端组件）
│   │   └── api/query/route.ts        # POST SSE 转发（runtime = "nodejs"）
│   ├── features/chat/
│   │   └── ChatPage.tsx              # "use client"，聊天交互与消息状态
│   ├── services/
│   │   └── query.ts                  # queryStream(query) — SSE 异步生成器
│   ├── styles/
│   │   └── style.css                 # 全局样式（CSS 变量 + 布局）
│   └── types/
│       └── query.ts                  # QueryEvent、ChatMessage、StepStatus
├── Dockerfile                        # 生产镜像：multi-stage build → standalone
├── Dockerfile.dev                    # 开发镜像：npm run dev + 挂载 ./frontend
├── next.config.ts                    # output: "standalone"
├── package.json
├── tsconfig.json                     # strict, noEmit, jsx: "react-jsx"
└── README.md
```

### 关键文件

- `src/features/chat/ChatPage.tsx` — 唯一客户端组件。`busy` ref 防止重复提交；`Enter` 键触发发送；`useEffect([messages])` 自动滚动到底部。
- `src/services/query.ts` — `queryStream(query)`：`fetch('/api/query')` → `getReader()` → 按 `\r?\n\r?\n` 切分事件 → 取 `data:` 行解析 `JSON`。解析失败的行静默忽略。
- `src/types/query.ts` — 与后端 SSE 契约保持一致：
  - `QueryEvent` = `{type: "progress", step, status}` | `{type: "result", data}` | `{type: "error", message}`
  - `ChatMessage` 是按 `message.type` 判别的联合类型：`text` / `steps` / `table` / `error`。
- `src/styles/style.css` — 唯一样式来源。常用 class：`.chat-page`、`.message-row`、`.bubble`、`.avatar`、`.steps`、`.step`、`.dot`、`.table-wrap`、`.result-table`、`.input-wrapper`、`.input-box`、`.error-text`。

## 请求流

1. 用户在 `ChatPage` 输入问题，回车或点击「发送」。新消息被追加为 `user` 文本气泡，并插入一个 `assistant` 占位气泡（`type: "steps"`）。
2. `queryStream(query)` POST `{ query }` 到相对路径 `/api/query`，读取 `response.body` 的 `getReader()`，按事件切分并 yield `QueryEvent`。
3. Next.js 路由处理器把请求转发到 `${API_BASE_URL ?? "http://localhost:8000"}/api/query`，透传 headers / status / body。`cache: "no-store"` 和 `signal: request.signal` 保留客户端断连。
4. `ChatPage` 根据事件类型更新气泡：
   - `progress` → 找到同名步骤，更新状态（`running` / `success` / `error`）；
   - `result` → 追加新的 `table` 气泡（`columns = Object.keys(data[0])`）；
   - `error` → 追加 `error` 气泡。

## 开发注意事项

- `tsconfig.json` 启用了 `strict` + `noEmit`，类型错误会直接阻塞 `tsc --noEmit` 与 `npm run build`。`.next/types/**/*.ts` 与 `.next/dev/types/**/*.ts` 是 Next.js 生成的类型文件，已被 git 忽略。
- `next.config.ts` 目前只有 `output: "standalone"`，生产 `Dockerfile` 依赖 `.next/standalone/server.js`；修改此配置前请阅读根 `AGENTS.md`。
- 无路径别名；统一使用相对路径（`../../services/query` 等）。
- 不要把 `response.body` 在路由处理器里 `await response.text()` —— SSE 必须流式透传。
- 修改 `src/types/query.ts` 时同步检查后端 `backend/app/services/query_service.py` 与 `backend/app/agent/nodes/*.py`。

## 与 Compose 的集成

`docker-compose.yml` 中 prod 前端：构建 `frontend/Dockerfile`，启动后从容器内 `:3000` 通过端口映射暴露到宿主机 `:8080`，环境变量 `API_BASE_URL=http://backend:8000`。

`docker-compose.dev.yml` 覆盖 prod frontend 服务：

- 使用 `frontend/Dockerfile.dev`；
- 启动命令 `npm run dev -- --hostname 0.0.0.0`；
- 环境变量 `NODE_ENV=development`、`WATCHPACK_POLLING=true`；
- 挂载 `./frontend:/app`（匿名卷覆盖 `node_modules` 与 `.next`，避免宿主机与容器依赖冲突）。

## 相关文档

- [frontend/AGENTS.md](AGENTS.md) — 编码 Agent 协作的详细指南
- [../README.md](../README.md) — 项目入口
- [../AGENTS.md](../AGENTS.md) — 仓库级 Agent 指南
- [../backend/README.md](../backend/README.md) — 后端文档
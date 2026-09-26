# 掌柜问数

自然语言查询数据的 Web 应用。前端使用 TypeScript、React 和 Next.js，后端使用 FastAPI；MySQL、Elasticsearch、Qdrant 和向量模型由 Docker Compose 编排。

## 目录

- `backend/app/`：API、依赖注入、业务服务、Agent、数据模型和数据访问层。
- `backend/scripts/`：后端元知识库初始化脚本。
- `frontend/`：Next.js 前端源码和构建配置。
- `infra/docker/`：MySQL 初始化 SQL。
- `docs/`：项目文档和目录规范。
- `scripts/`：跨服务检查脚本。

目录按 `docs/ARCHITECTURE_INSTRUCTIONS.md` 整理。没有对应业务内容的参考目录未创建。

## 一键开发启动

1. 从 `.env.example` 创建 `.env`，填入 `DEEPSEEK_API_KEY`，并启动 Docker Desktop。
2. 在项目根目录运行 `make dev`（`make up` 相同）。命令会启动前端、后端、MySQL、Elasticsearch、Qdrant、向量服务及元知识库初始化。
3. 打开 <http://localhost:8080>。前端运行 Next.js 开发服务器，修改 `frontend/` 源码后会热更新，无需重新构建镜像。

首次启动需要下载镜像和中文向量模型，并等待元知识库初始化完成。用 `make ps` 查看状态，`make logs` 查看日志，`make logs SERVICE=frontend` 只看前端日志。`make smoke` 检查前后端 HTTP 响应；`make typecheck` 检查前端类型；`make stop`（或 `make down`）停止服务并保留容器和数据卷。运行 `make help` 查看全部命令。

## Docker 生产启动

1. 从 `.env.example` 创建 `.env`，填入 `DEEPSEEK_API_KEY`。
2. 运行 `make prod`。
3. 打开 <http://localhost:8080>。

Compose 使用 `backend/app/core/config/app_config.example.yaml` 作为基础配置，并通过环境变量注入服务地址、数据库密码和 API 密钥。不要把真实密钥写入该模板。

## 本地开发

后端固定使用 Python 3.11.2。将 `backend/app/core/config/app_config.example.yaml` 复制为同目录的 `app_config.yaml`，按本地环境修改，然后在 `backend/` 运行 `uv sync` 和 `uv run uvicorn app.main:app --reload`。本地配置文件被 Git 和 Docker 构建忽略。

前端：在 `frontend/` 运行 `npm ci` 和 `npm run dev`，访问 <http://localhost:3000>。Next.js 的 `/api/query` 路由将请求转发到本机 `8000` 端口；可用 `API_BASE_URL` 指定其他后端地址。

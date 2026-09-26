# 掌柜问数

自然语言查询数据的 Web 应用。用户在前端输入中文问题，后端 LangGraph Agent 从 MySQL 元数据库 / Qdrant 向量库 / Elasticsearch 全文索引中检索相关表、字段和指标，结合 LLM 生成并校验 SQL，最终在数据仓库 MySQL 上执行并以 SSE 流式返回结果表格。

- 前端：TypeScript + React 19 + Next.js 16（App Router）
- 后端：Python 3.11 + FastAPI + LangGraph + SQLAlchemy（asyncmy）
- 依赖服务：MySQL 8.4（`meta` + `dw` 双库）、Elasticsearch 8.19、Qdrant 1.16、text-embeddings-inference（`BAAI/bge-large-zh-v1.5`）
- LLM：DeepSeek（`deepseek-flash`）
- 编排：Docker Compose（dev / prod 两个 Compose 文件 + Makefile 命令面）

外部访问入口：[http://localhost:8080](http://localhost:8080)（前端 Next.js，端口 8080 → 容器内 3000）。

## 架构

### 服务拓扑

| 服务 | 镜像 / 构建 | 暴露端口 | 说明 |
| --- | --- | --- | --- |
| `mysql` | `mysql:8.4` | 容器内 3306 | `meta` + `dw` 两个数据库，从 `infra/docker/mysql/init.sql` 初始化 |
| `elasticsearch` | `docker.elastic.co/elasticsearch/elasticsearch:8.19.3` | 容器内 9200 | 单节点、关闭安全策略，存储字段取值全文索引 |
| `qdrant` | `qdrant/qdrant:v1.16.2` | 容器内 6333 | 字段、指标的向量索引（cosine, dim 1024） |
| `embeddings` | `ghcr.io/huggingface/text-embeddings-inference:cpu-arm64-1.9` | 容器内 80 | 提供 `BAAI/bge-large-zh-v1.5` 向量服务 |
| `knowledge-init` | `./backend/Dockerfile`（`restart: no`） | — | 等待依赖就绪后执行 `scripts.wait_and_build_meta`；`/state/ready` 已存在则跳过 |
| `backend` | `./backend/Dockerfile` | 容器内 8000 | FastAPI + uvicorn，仅在 MySQL 健康且 `knowledge-init` 成功后启动 |
| `frontend` | `frontend/Dockerfile`（prod） / `Dockerfile.dev` | 8080 → 3000 | Next.js；dev Compose 挂载源码支持 HMR |

`docker-compose.yml` 与 `docker-compose.dev.yml` 共享一份 `&backend-environment` YAML 锚点，把 MySQL/Qdrant/ES/Embeddings/DeepSeek 的连接信息同时注入 `knowledge-init` 和 `backend`。

### 请求链路

```
Browser (8080)
  → frontend/src/app/api/query/route.ts   ← SSE 代理
  → backend POST /api/query
  → QueryService.query
  → LangGraph graph.astream(stream_mode="custom")
        extract_keywords → recall_column / recall_value / recall_metric
        → merge_retrieved_info → filter_table / filter_metric
        → add_extra_context → generate_sql → validate_sql → (correct_sql) → execute_sql
  → StreamingResponse(text/event-stream) → 前端 ChatPage 渲染
```

后端只读取 `dw` 数据仓库（`execute_sql`、`validate_sql` 都对它跑 `EXPLAIN` + `SELECT`）。`meta` 仅用于保存元知识（表、字段、指标、字段-指标关系）。前端是 Next.js 服务端组件 + 一个 SSE 转发路由（`runtime = "nodejs"`）。

## 仓库结构

```
.
├── backend/        FastAPI + LangGraph Agent（详见 backend/README.md、backend/AGENTS.md）
├── frontend/       Next.js 聊天页（详见 frontend/README.md、frontend/AGENTS.md）
├── infra/
│   └── docker/mysql/init.sql        DW 种子数据 + meta 库 DDL，首次启动 MySQL 时执行
├── docs/           项目规范（ARCHITECTURE_INSTRUCTIONS、COMMIT_INSTRUCTIONS 等）
├── scripts/
│   └── smoke.sh    HTTP 探活脚本（make smoke）
├── docker-compose.yml
├── docker-compose.dev.yml
├── Makefile
├── .env.example
├── AGENTS.md       编码 Agent 协作指南（根）
└── README.md
```

`tests/`、`components/`、`hooks/`、`stores/`、`utils/`、`migrations/` 等顶层目录按 `docs/ARCHITECTURE_INSTRUCTIONS.md` 约定：**仅在出现真实业务内容时创建**，目前不存在。

## 前置条件

- Docker Desktop（Compose 编排需要）
- `make`（根 Makefile 是唯一的命令面）
- 一个 DeepSeek API Key（写入 `.env` 的 `DEEPSEEK_API_KEY`）
- 本地（非 Docker）后端开发：Python 3.11.2（与 `backend/.python-version`、`backend/pyproject.toml` 的 `>=3.11.2,<3.12` 完全一致）
- 本地（非 Docker）前端开发：Node 22（匹配 Dockerfile）

## 快速开始

### 1. 准备环境

```bash
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY；其它变量使用默认值即可
```

启动 Docker Desktop。

### 2. 启动开发栈

```bash
make dev       # 或 make up；别名相同
```

首次启动会拉取镜像、下载 BGE 中文向量模型（数百 MB）、等待 MySQL 种子完成，然后跑 `knowledge-init` 构建元知识库。观察进度：

```bash
make ps        # 查看各服务状态
make logs      # 跟踪日志
make logs SERVICE=frontend   # 只看前端
make logs SERVICE=knowledge-init   # 查看元知识库初始化
```

启动完成后访问 [http://localhost:8080](http://localhost:8080)。前端容器挂了源码（`./frontend:/app`，`WATCHPACK_POLLING=true`），修改前端文件会热更新；后端在 Compose 中**不**启用 `--reload`，需 `make restart SERVICE=backend` 才能让后端改动生效。

### 3. 生产启动

```bash
make prod
```

使用 `docker-compose.yml` 中的 `frontend/Dockerfile`（多阶段构建 standalone 镜像），不挂载源码。

### 4. 验证

```bash
make smoke     # 检查前端 /、后端 /openapi.json、POST /api/query 校验（详见 scripts/smoke.sh）
make typecheck # exec 进前端容器跑 tsc --noEmit
```

## 配置

### 运行时环境变量（`.env`）

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek 平台密钥；Compose 会注入 `knowledge-init` 和 `backend` |
| `MYSQL_ROOT_PASSWORD` | — | MySQL `root` 密码，默认 `local-root-password` |
| `DATA_AGENT_DB_PASSWORD` | — | MySQL 应用用户 `atguigu` 密码，默认 `Atguigu.123` |

`.env` 被 git 忽略（`.env*`），请勿提交。

### 后端 YAML

- `backend/app/core/config/app_config.yaml` — 提交到 git 的基础配置，Compose 和本地开发共用。
- API key 等秘密不要写入这个文件；通过 `.env` 或环境变量提供。运行时通过 `DATA_AGENT_DB_*` / `DATA_AGENT_QDRANT_*` / `DATA_AGENT_EMBEDDING_*` / `DATA_AGENT_ES_*` / `DATA_AGENT_LLM_API_KEY` 覆盖 YAML 中的字段。`app/core/config/app_config.py` 集中处理。

### 元知识源

`backend/app/core/config/meta_config.yaml` 定义了表、字段、字段角色、字段类型、字段别名、字段示例以及指标、指标的关联字段、指标别名。`knowledge-init` 服务调用 `MetaKnowledgeService.build` 据此写入 `meta` MySQL（结构化元数据）、Qdrant（字段 / 指标向量）、Elasticsearch（`sync: true` 列的取值全文索引）。`knowledge-init` 通过 `knowledge_state` 卷上的 `/state/ready` 文件做幂等控制；新增 / 修改表或指标后需要删除这个标记重建：

```bash
make stop
docker volume rm data-agent_knowledge_state   # 容器卷名带项目前缀
make dev
```

### 前端后端地址

`API_BASE_URL`（服务端环境变量），默认 `http://localhost:8000`；Compose 内置 `http://backend:8000`。仅在 `frontend/src/app/api/query/route.ts`（Node 运行时）中读取，不会泄漏到客户端 bundle。

## 常用命令

| 目标 | 命令 |
| --- | --- |
| 启动开发栈（HMR 前端） | `make dev` / `make up` |
| 启动生产栈 | `make prod` |
| 停止（保留卷与容器） | `make stop` / `make down` |
| 重启 | `make restart [SERVICE=backend]` |
| 查看状态 | `make ps` |
| 跟踪日志 | `make logs [SERVICE=frontend]` |
| HTTP 探活 | `make smoke` |
| 前端类型检查 | `make typecheck` |
| 构建生产镜像 | `make build` |
| 列出所有命令 | `make help` |

后端 / 前端各自的原生开发命令详见 `backend/README.md` 与 `frontend/README.md`。

## API 契约

- `POST /api/query`（前端 Next.js 路由 → 后端）请求体 `{ "query": string }`，响应 `text/event-stream`。
- 每个事件格式：`data: <json>\n\n`，前端解析器（`frontend/src/services/query.ts`）忽略无法解析的事件。
- 事件类型（`frontend/src/types/query.ts`，由后端 `QueryService` 生成）：
  - `{ "type": "progress", "step": string, "status": "running" | "success" | "error" }`
  - `{ "type": "result", "data": Record<string, unknown>[] }`
  - `{ "type": "error", "message": string }`

## 关键特性

- **元知识驱动的检索**：`meta_config.yaml` 是元数据唯一来源；启动时由 `knowledge-init` 一次性构建 `meta` MySQL、`data-agent-column` / `data-agent-metric` Qdrant collection、`data-agent-value` ES 索引。
- **LangGraph 多路召回 + 过滤 + 校验**：并行召回字段 / 字段取值 / 指标；合并后用 LLM 过滤；调用 LLM 生成 SQL；`EXPLAIN` 校验失败会进入 `correct_sql` 节点重试；最终 `execute_sql` 输出 `result`。
- **SSE 流式体验**：每完成一个节点都向浏览器推一个 `progress` 事件，`result` 事件携带结果表行。
- **生产级 Dockerfile**：后端使用 `python:3.11.2-bullseye` + uv + `uv sync --frozen`；前端使用 Next.js standalone 输出。

## 模块文档

- [frontend/README.md](frontend/README.md) — 前端栈、命令、路由、环境变量、源码结构
- [backend/README.md](backend/README.md) — 后端架构、组件、配置、运行、源码结构
- [AGENTS.md](AGENTS.md) — 编码 Agent 协作的根指南
- [backend/AGENTS.md](backend/AGENTS.md) / [frontend/AGENTS.md](frontend/AGENTS.md) — 模块级 Agent 指南

# backend

Python 3.11 + FastAPI 实现的自然语言查询后端。核心是一个 LangGraph Agent，从 MySQL 元数据库（结构化元数据）、Qdrant（字段 / 指标向量）、Elasticsearch（字段取值全文索引）中多路召回，再用 LLM 过滤、生成 SQL、对 DW MySQL 跑 `EXPLAIN` 校验，必要时进入校正循环，最终 `execute_sql` 把结果以 SSE 事件流式返回给前端。

| 关注点 | 技术 |
| --- | --- |
| 语言 | Python 3.11.2（pinned in `.python-version`） |
| 包管理 | uv（`uv.lock` 已提交；`uv sync --frozen`） |
| Web 框架 | FastAPI（`fastapi[standard]>=0.128`） + uvicorn |
| 数据库驱动 | asyncmy + SQLAlchemy 2.x 异步 |
| 向量库 | Qdrant（`qdrant-client` async） |
| 全文索引 | Elasticsearch 8（`elasticsearch[async]>=8,<9`） |
| Agent | LangGraph `StateGraph` + LangChain |
| LLM | DeepSeek（`langchain-deepseek` / `ChatOpenAI` 指向 `https://api.deepseek.com`，模型 `deepseek-flash`） |
| 向量模型 | `BAAI/bge-large-zh-v1.5`（通过 HuggingFace `text-embeddings-inference`，dim 1024） |
| 配置 | OmegaConf 合并 dataclass schema + YAML + 环境变量 |
| 日志 | loguru（`app/core/log.py`），每个请求通过 `request_id` ContextVar 注入 |

## 先决条件

- Python **3.11.2**（严格匹配 `backend/.python-version` 与 `backend/pyproject.toml` 的 `>=3.11.2,<3.12`）
- [uv](https://docs.astral.sh/uv/)（`Dockerfile` 内使用 `ghcr.io/astral-sh/uv:0.12.17`）
- 一个 DeepSeek API Key（写入 `.env` 的 `DEEPSEEK_API_KEY`，或环境变量 `DATA_AGENT_LLM_API_KEY`）
- 本地依赖服务（仅在脱离 Compose 启动时需要）：
  - MySQL 8.4（已用 `infra/docker/mysql/init.sql` 初始化 `meta` + `dw` 两个库）
  - Elasticsearch 8.x（关闭安全策略）
  - Qdrant 1.16+
  - `text-embeddings-inference` 服务（默认 `http://localhost:8081`）

> 推荐直接使用根目录 `make dev` 启动完整栈；只有需要独立调试后端时才用下面的原生命令。

## 安装

```bash
cd backend
uv sync
```

## 配置

### `app_config.yaml`（运行时配置）

`app/core/config/app_config.yaml` 是仓库跟踪的基础配置，Compose 与本地原生开发共用。不要在其中填写真实 API key 或密码；通过 `.env` 或环境变量提供秘密，并按需覆盖主机名和端口。

配置加载时会读取项目根目录的 `.env`。Compose 或 shell 已注入的环境变量优先于 `.env` 中的值。

### `meta_config.yaml`（元知识源）

`app/core/config/meta_config.yaml` 是元数据知识库的唯一来源：

- `tables`：每个表名、`role`（`dim` / `fact`）、描述、字段列表（每个字段含 `name`、`role`、`description`、`alias`、`sync`）；
- `metrics`：指标名、描述、`relevant_columns`（如 `fact_order.order_amount`）、别名。

`knowledge-init` 服务调用 `MetaKnowledgeService.build(config_path)` 据此：

1. 把 `table_info` / `column_info` / `metric_info` / `column_metric` 写入 `meta` MySQL；
2. 把字段和指标的 `name` / `description` / `alias` 编码为向量，写入 Qdrant collection（`data-agent-column`、`data-agent-metric`）；
3. 把 `sync: true` 列的取值去重后写入 Elasticsearch 索引 `data-agent-value`。

修改此文件后必须重新构建元知识（见下文「运行」一节）。

### 环境变量覆盖

`app/core/config/app_config.py` 在加载 YAML 之后按以下变量覆盖：

| 环境变量 | 默认来源 |
| --- | --- |
| `DATA_AGENT_DB_META_HOST` / `_PORT` / `DATA_AGENT_DB_USER` / `DATA_AGENT_DB_PASSWORD` | `app_config.db_meta.*` |
| `DATA_AGENT_DB_DW_HOST` / `_PORT` | `app_config.db_dw.*` |
| `DATA_AGENT_QDRANT_HOST` / `_PORT` | `app_config.qdrant.*` |
| `DATA_AGENT_EMBEDDING_HOST` / `_PORT` | `app_config.embedding.*` |
| `DATA_AGENT_ES_HOST` / `_PORT` | `app_config.es.*` |
| `DATA_AGENT_LLM_API_KEY`（回退 `DEEPSEEK_API_KEY`） | `app_config.llm.api_key` |

`meta_config.yaml` **不**受环境变量覆盖——它是元知识源。

### Qdrant / ES 命名

- Qdrant collections：`data-agent-column`、`data-agent-metric`（dim 1024，cosine）。
- ES index：`data-agent-value`。
- 向量维度 = `app_config.qdrant.embedding_size = 1024`，与 `BAAI/bge-large-zh-v1.5` 对齐。

## 运行

### 1. 构建元知识库（首次或修改 `meta_config.yaml` 后）

```bash
# 推荐方式：删除 knowledge_state 卷上的 /state/ready 标记后 make dev，让 knowledge-init 自动重建
make stop
docker volume rm data-agent_knowledge_state   # 容器卷名带项目前缀
make dev

# 或者直接重跑脚本（绕过卷标记）：
uv run python -m scripts.wait_and_build_meta
```

`scripts.wait_and_build_meta` 会先 `SELECT COUNT(*) FROM fact_order`（确认 DW 已 seed）、然后 `GET /health` 探活 ES / Qdrant / embeddings（Compose 内对应 `http://elasticsearch:9200/`、`http://qdrant:6333/healthz`、`http://embeddings:80/health`），全部就绪后再触发 build。`knowledge-init` Compose 服务通过 `/state/ready` 卷文件实现幂等——文件存在则跳过。

### 2. 启动 API

```bash
uv run uvicorn app.main:app --reload
# 默认 0.0.0.0:8000
```

`app/main.py` 注册了一个 HTTP 中间件，在每次请求时把 `uuid4()` 写入 `request_id_ctx_var`，由 `app/core/log.py` 注入 loguru 日志格式；`app/core/lifespan.py` 在启动 / 关闭时 `init()` / `close()` 所有 client manager。

### 3. 调用 API

```bash
curl -N -H 'Content-Type: application/json' \
  -d '{"query":"统计去年各地区的销售总额"}' \
  http://localhost:8000/api/query
```

响应是 `text/event-stream`，每个事件形如：

```
data: {"type": "progress", "step": "抽取关键字", "status": "running"}

data: {"type": "progress", "step": "抽取关键字", "status": "success"}

...

data: {"type": "result", "data": [{"region_name": "华南", "GMV": 12345.67}, ...]}
```

## 命令

| 目标 | 命令 |
| --- | --- |
| 安装依赖 | `uv sync` |
| 启动 API（hot reload） | `uv run uvicorn app.main:app --reload` |
| 构建元知识库 | `uv run python -m scripts.build_meta_knowledge --conf app/core/config/meta_config.yaml` |
| 等待依赖 + 构建 | `uv run python -m scripts.wait_and_build_meta` |
| 类型检查 | 未配置（项目按 dataclass + TypedDict 风格书写） |
| 代码格式化 / Lint | 未配置（依赖 `make smoke` 进行 HTTP 验证） |

仓库根目录快捷方式：`make dev` / `make prod` / `make restart SERVICE=backend` / `make logs SERVICE=backend` / `make logs SERVICE=knowledge-init` / `make smoke`。

## 架构

### 组件分层

```
app/
├── main.py                              FastAPI app + request_id 中间件
├── api/routers/query_router.py          POST /api/query → StreamingResponse
├── schemas/query_schema.py              Pydantic 请求 schema (QuerySchema{ query: str })
├── dependencies/query.py                FastAPI Depends：session / repo / service
├── services/
│   ├── query_service.py                 QueryService.query：构建上下文，astream graph
│   └── meta_knowledge_service.py        MetaKnowledgeService.build：构建 meta 库
├── agent/
│   ├── graph.py                         StateGraph 编译入口
│   ├── state.py                         DataAgentState TypedDict
│   ├── context.py                       DataAgentContext TypedDict
│   ├── llm.py                           ChatOpenAI 实例（DeepSeek）
│   ├── prompt_loader.py                 load_prompt(name)：读 prompts/<name>.md
│   ├── nodes/                           12 个节点（见下）
│   └── prompts/                         7 个 Markdown 提示词模板
├── core/
│   ├── config/                          OmegaConf dataclass schema + YAML + env
│   ├── clients/embedding_client_manager.py  HuggingFaceEndpointEmbeddings 包装
│   ├── lifespan.py                      FastAPI lifespan：init/close 全部 client
│   ├── log.py                           loguru 配置 + request_id 注入
│   └── context.py                       request_id ContextVar
├── db/                                  MySQL / Qdrant / ES client managers
├── repositories/
│   ├── mysql/dw/dw_mysql_repository.py  show columns、distinct values、EXPLAIN、execute
│   ├── mysql/meta/meta_mysql_repository.py + mappers/  table/column/metric CRUD
│   ├── qdrant/column_qdrant_repository.py     data-agent-column collection
│   ├── qdrant/metric_qdrant_repository.py     data-agent-metric collection
│   └── es/value_es_repository.py             data-agent-value index
├── entities/                            框架无关 dataclass（agent 内部流转）
└── models/                              SQLAlchemy ORM（meta DB only）
scripts/
├── build_meta_knowledge.py              MetaKnowledgeService.build 包装
└── wait_and_build_meta.py               轮询依赖 + 触发 build
```

`app/` 是 PEP 420 隐式命名空间包，**不要**添加 `__init__.py`。

### Agent 拓扑（LangGraph）

`DataAgentState`（`app/agent/state.py`）：`query`、`keywords`、`retrieved_columns`、`retrieved_values`、`retrieved_metrics`、`table_infos`、`metric_infos`、`date_info`、`db_info`、`sql`、`error`。

`DataAgentContext`（`app/agent/context.py`）：`embedding_client`、`column_qdrant_repository`、`value_es_repository`、`metric_qdrant_repository`、`meta_mysql_repository`、`dw_mysql_repository`。

图（`app/agent/graph.py`）：

```
START → extract_keywords
        ├→ recall_column ─┐
        ├→ recall_value  ─┼→ merge_retrieved_info → filter_table   ─┐
        └→ recall_metric ─┘                  └→ filter_metric ─┘ → add_extra_context
                                                                       → generate_sql
                                                                       → validate_sql
                                                                          ├─ (error is None) → execute_sql → END
                                                                          └─ (error != None) → correct_sql → execute_sql → END
```

每个节点调用 `runtime.stream_writer({"type": "progress", "step": "...", "status": "running|success|error"})` 把进度推送成 SSE 事件；只有 `execute_sql` 发送 `{"type": "result", "data": [...]}`。

节点清单（`app/agent/nodes/`）：`extract_keywords`、`recall_column`、`recall_value`、`recall_metric`、`merge_retrieved_info`、`filter_table`、`filter_metric`、`add_extra_context`、`generate_sql`、`validate_sql`、`correct_sql`、`execute_sql`。

提示词（`app/agent/prompts/`，纯文本）：`generate_sql`、`correct_sql`、`extend_keywords_for_column_recall`、`extend_keywords_for_value_recall`、`extend_keywords_for_metric_recall`、`filter_table_info`、`filter_metric_info`。中文提示词，请保留原文措辞。

### 仓储约定

- `app/entities/*.py` 是 framework-free dataclass，用于在 Agent 状态中流转，也用于 Qdrant / ES payload；
- `app/models/*.py` 是 `meta` DB 的 SQLAlchemy ORM 模型；
- `app/repositories/mysql/meta/mappers/*.py` 在 entity ↔ model 之间转换（用 `asdict()`）；
- repositories 通过 `app/dependencies/query.py` 注入；除 `lifespan` / `scripts` 外，不要直接调用 client managers；
- 新增协作者请把它注册到 `get_query_service` 上游，避免在路由中直接 `new`。

### 请求入口

`app/services/query_service.py` 是唯一入口：

```python
async def query(self, query: str):
    context = DataAgentContext(...)
    state = DataAgentState(query=query)
    try:
        async for chunk in graph.astream(
            input=state, context=context, stream_mode="custom"
        ):
            yield f"data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False, default=str)}\n\n"
```

每个请求都会构建一个全新的 `DataAgentContext` 与 `DataAgentState`，**不要**跨请求缓存状态。`default=str` 是为了让 MySQL `Decimal` 等非 JSON 原生类型顺利序列化。

## 测试与验证

项目没有单元测试套件（按 `docs/ARCHITECTURE_INSTRUCTIONS.md`，仅在有真实业务内容时创建 `tests/`）。通过以下方式验证：

- `make smoke`（`scripts/smoke.sh`）—— 检查前端 `/`、后端 `/openapi.json` 含 `/api/query`、`POST /api/query {}` 返回 `422`（Pydantic 校验失败）。
- `make logs SERVICE=backend` —— 查看节点级 progress 事件、生成的 SQL、执行结果。
- `make logs SERVICE=knowledge-init` —— 确认元知识库首次构建成功；之后会有 `Metadata knowledge is already initialized.` 跳过日志。
- 手动：`curl -N -H 'Content-Type: application/json' -d '{"query":"..."}' http://localhost:8000/api/query`。

## 代码风格

- `app/` 内的注释与 docstring 为中文；编辑 `app/agent/prompts/*.md` 时保持中文措辞。
- 4 空格缩进，类型用 `TypedDict` / dataclass；项目未启用 `from __future__ import annotations`，保持 Python 3.11 习惯写法。
- **不要**在 `app/` 内放 `__init__.py`。
- **不要**提交 `.env`、真实 API key 或密码；`app_config.yaml` 只保留可共享的基础配置。
- 新增节点请沿用现有模式：`runtime.stream_writer` 推送 progress → `try / except` → `logger.info` 成功日志 → 失败时 `raise`。
- 编辑完成后用 `make smoke` 跑一次端到端验证。

## 重要不变量

- **Embedding 维度 = 1024**：与 `BAAI/bge-large-zh-v1.5` 一致。`app_config.qdrant.embedding_size` 与 Qdrant collection 的 `VectorParams.size` 必须同步；切换模型时同时改两边。
- **Qdrant / ES 命名**：collection / index 名称硬编码于 repositories；改名需要重建卷。
- **`knowledge-init` 幂等**：通过 `knowledge_state` 卷上的 `/state/ready` 标记实现；需要重建请 `docker volume rm data-agent_knowledge_state`（卷名带项目前缀，可用 `docker volume ls` 查询）。
- **SQL 校验**：`DWMySQLRepository.validate_sql` 通过 `EXPLAIN <sql>` 校验；失败会写 `state["error"]` 并路由到 `correct_sql`，再回到 `execute_sql`。
- **只读执行**：所有 `INSERT/UPDATE/DELETE/CREATE` 由 `app/agent/prompts/*.md` 显式禁止；仓储层不做强制。
- **`extract_keywords` POS allowlist**：`extract_keywords.py` 的 `allow_pos` tuple 控制哪些 jieba 词性到达 recallers；新增词性会改变召回行为，请谨慎。
- **请求级状态**：每个请求的新 `DataAgentContext` / `DataAgentState`，不要跨请求共享。
- **JSON 序列化**：`QueryService` 使用 `default=str`，`MetaKnowledgeService._save_tables_to_meta_db` 已对 MySQL `Decimal` 做 `float` 强制转换，确保 `column_info.examples` JSON 列能正常存储。

## 相关文档

- [backend/AGENTS.md](AGENTS.md) — 编码 Agent 协作的详细指南
- [../README.md](../README.md) — 项目入口
- [../AGENTS.md](../AGENTS.md) — 仓库级 Agent 指南
- [../frontend/README.md](../frontend/README.md) — 前端文档

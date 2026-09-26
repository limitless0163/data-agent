# backend/AGENTS.md

Agent guidance for the Python FastAPI backend.

For repo-wide orientation (Compose topology, env vars, Make targets), see [AGENTS.md](../AGENTS.md).

## Stack

- Python **3.11.2** (pinned in `backend/.python-version`; `pyproject.toml` requires `>=3.11.2,<3.12`).
- Package manager: **uv** (`uv.lock` is committed; do not hand-edit — run `uv lock` if you need to update deps).
- Web: **FastAPI** (`fastapi[standard]>=0.128`), async uvicorn on port `8000`, host `0.0.0.0`.
- Async DB driver: **asyncmy** + SQLAlchemy 2.x (`mysql+asyncmy://...`).
- Vector store: **Qdrant** (`qdrant-client` async).
- Search: **elasticsearch[async]>=8,<9`.
- LLM: **DeepSeek** (`langchain-deepseek` exposed as a `ChatOpenAI` against `https://api.deepseek.com`; model `deepseek-flash`; `extra_body={"thinking": {"type": "disabled"}}`).
- Embeddings: **`HuggingFaceEndpointEmbeddings`** pointed at the `embeddings` container (the local `text-embeddings-inference` server, model `BAAI/bge-large-zh-v1.5`, dim 1024).
- Agent runtime: **langgraph** (`StateGraph`).
- Logging: **loguru** with per-request `request_id` (`app.core.context` + `app.core.log`).
- Config: **OmegaConf** (`app.core.config.app_config`) merging a typed dataclass schema with YAML, then env-var overrides.

## Commands

Run from `backend/` unless noted.

| Goal                          | Command                                                            |
| ----------------------------- | ------------------------------------------------------------------ |
| Install deps                  | `uv sync`                                                          |
| Run API (hot reload, native)  | `uv run uvicorn app.main:app --reload`                             |
| Run knowledge base build      | `uv run python -m scripts.build_meta_knowledge --conf app/core/config/meta_config.yaml` |
| Wait for deps + build meta    | `uv run python -m scripts.wait_and_build_meta` (Compose `knowledge-init` does this) |
| Standalone lint/format        | none wired in; the repo relies on Docker smoke + `make smoke`      |
| Type-check                    | not configured (Python is untyped by design here; follow dataclass patterns) |

`make dev`, `make prod`, `make logs`, `make ps`, `make smoke`, `make restart` from the repo root drive the Compose setup.

## Source layout

```
app/
├── main.py                              # FastAPI app + request_id middleware
├── api/routers/query_router.py          # POST /api/query → StreamingResponse
├── dependencies/query.py                # FastAPI Depends providers for repos/services
├── schemas/query_schema.py              # Pydantic request schema
├── services/
│   ├── query_service.py                 # Builds DataAgentContext, astreams the graph
│   └── meta_knowledge_service.py        # Builds meta knowledge from meta_config.yaml
├── agent/
│   ├── graph.py                         # Compiles the LangGraph state graph
│   ├── state.py                         # DataAgentState TypedDict
│   ├── context.py                       # DataAgentContext TypedDict
│   ├── llm.py                           # Shared ChatOpenAI instance (DeepSeek)
│   ├── prompt_loader.py                 # load_prompt(name) reads prompts/<name>.prompt
│   ├── nodes/                           # 12 graph nodes
│   └── prompts/                         # 7 prompt templates (plain text)
├── core/
│   ├── config/
│   │   ├── app_config.{yaml,py}         # Runtime config (DB/Qdrant/ES/embeddings/LLM/logging)
│   │   ├── app_config.example.yaml      # Checked-in template (read-only inside Compose)
│   │   └── meta_config.{yaml,py}        # Meta knowledge source
│   ├── clients/embedding_client_manager.py  # Wraps HuggingFaceEndpointEmbeddings
│   ├── lifespan.py                      # init/close all client managers on FastAPI startup/shutdown
│   ├── log.py                           # loguru setup with request_id injection
│   └── context.py                       # request_id ContextVar
├── db/
│   ├── mysql_client_manager.py          # meta + dw async engines (pool_size=10, pool_pre_ping)
│   ├── qdrant_client_manager.py
│   └── es_client_manager.py
├── repositories/
│   ├── mysql/
│   │   ├── dw/dw_mysql_repository.py        # Read column types/values; EXPLAIN-validate; execute SQL
│   │   └── meta/
│   │       ├── meta_mysql_repository.py     # CRUD table/column/metric; get_key_columns_by_table_id
│   │       └── mappers/*.py                 # Entity ↔ ORM converters
│   ├── qdrant/{column,metric}_qdrant_repository.py
│   └── es/value_es_repository.py            # Value full-text index
├── entities/                            # Plain dataclasses (no ORM, JSON-friendly)
└── models/                              # SQLAlchemy ORM models (meta DB)
scripts/
├── build_meta_knowledge.py              # Initializes managers + invokes MetaKnowledgeService
└── wait_and_build_meta.py               # Polls MySQL/ES/Qdrant/embeddings, then builds
tests/                                    # 后端单元测试、接口测试
Dockerfile                                # python:3.11.2-bullseye + uv + uvicorn
pyproject.toml                            # PEP 621 deps
```

## Agent topology (LangGraph)

State schema (`app/agent/state.py`): `query`, `keywords`, `retrieved_columns`, `retrieved_values`, `retrieved_metrics`, `table_infos`, `metric_infos`, `date_info`, `db_info`, `sql`, `error`.

Compiled in `app/agent/graph.py`:

```
START → extract_keywords
        ├→ recall_column ─┐
        ├→ recall_value  ─┼→ merge_retrieved_info → filter_table   ─┐
        └→ recall_metric ─┘                  └→ filter_metric ─┘ → add_extra_context
                                                                        → generate_sql
                                                                        → validate_sql ─(error? correct_sql : execute_sql)
                                                                        → correct_sql → execute_sql → END
```

Conditional edge at `validate_sql`: routes to `execute_sql` if `state["error"] is None`, else `correct_sql` (which then always flows to `execute_sql`).

Each node writes progress events via `runtime.stream_writer({"type": "progress", "step": "...", "status": "running|success|error"})` — these become the SSE `progress` events. Only `execute_sql` emits `result` (`{"type": "result", "data": [...]}`).

`QueryService.query` (`app/services/query_service.py`) is the only entry point. It builds a fresh `DataAgentContext` per request, invokes `graph.astream(input=DataAgentState(query=...), context=..., stream_mode="custom")`, and wraps each chunk as `data: <json>\n\n`.

## Repository conventions

- **PEP 420 namespace packages**: `app/` has no `__init__.py`. Do not add one. Modules resolve as `app.<sub>.<module>`.
- **Entities vs models**: `app/entities/*.py` are framework-free dataclasses (what flows through agents and into Qdrant/ES payloads). `app/models/*.py` are SQLAlchemy ORM models for the `meta` DB only. Mappers in `app/repositories/mysql/meta/mappers/` bridge them.
- **Mappers**: always convert via `asdict()` to/from models; do not store ORM instances in agent state.
- **Repositories**: one per backing store; clients are injected via constructors (see `app/dependencies/query.py`). Do not call client managers directly outside `lifespan`/`scripts`.
- **Dependency injection**: `app.dependencies.query` provides async generators for MySQL sessions, repositories, and `QueryService`. Compose `get_query_service` whenever you add a new collaborator — do not instantiate in routes.
- **Prompt loading**: `app/agent/prompt_loader.load_prompt(name)` reads `app/agent/prompts/<name>.prompt` as UTF-8. Keep prompts as plain text files; do not inline them in Python.
- **JSON serialization**: agent state values (notably `Decimal` from MySQL) need `default=str` when emitting SSE — `QueryService` already does this. Do not regress it (see `meta_knowledge_service._save_tables_to_meta_db` for the `Decimal → float` coercion that fixes the column examples JSON column).

## Configuration & environment

- `app/core/config/app_config.py` merges:
  1. `app_config.yaml` (loaded from `Path(__file__).with_name('app_config.yaml')` — falls back to example if no local copy),
  2. env-var overrides: `DATA_AGENT_DB_META_HOST/PORT`, `DATA_AGENT_DB_DW_HOST/PORT`, `DATA_AGENT_DB_USER`, `DATA_AGENT_DB_PASSWORD`, `DATA_AGENT_QDRANT_HOST/PORT`, `DATA_AGENT_EMBEDDING_HOST/PORT`, `DATA_AGENT_ES_HOST/PORT`, `DATA_AGENT_LLM_API_KEY` (falls back to `DEEPSEEK_API_KEY`).
- `meta_config.yaml` is NOT overridden by env vars — it is the schema knowledge source loaded by `scripts.wait_and_build_meta` → `MetaKnowledgeService.build`.
- Local dev: copy `app_config.example.yaml` → `app_config.yaml` (git-ignored, `.dockerignore`-ignored) and edit. Inside Compose, the example is mounted read-only; env vars supply everything.
- `app_config.embedding.port` default in the example file is `8081`, but inside Compose it is overridden to `80` (the HF text-embeddings-inference default).

## Important invariants

- **Embedding size = 1024**: matches `BAAI/bge-large-zh-v1.5`. Both `app_config.qdrant.embedding_size` and the Qdrant collection vector size must agree. If you swap the embedding model, update both.
- **Qdrant collection names**: `data-agent-column`, `data-agent-metric`. ES index: `data-agent-value`. Changing these requires deleting the volumes or migrating manually.
- **`knowledge-init` one-shot**: `docker-compose.yml` guards the meta build with `/state/ready` (`knowledge_state` volume). To rebuild, `make down -v` (drops volumes) or just delete `knowledge_state` and `make dev` again. Hitting `/api/query` before init finishes will fail because Qdrant/ES/meta-DB are empty.
- **SQL validation**: `DWMySQLRepository.validate_sql` runs `EXPLAIN <sql>` against the DW. `validate_sql` returning an exception populates `state["error"]` and routes to `correct_sql` — the corrector's prompt lives at `app/agent/prompts/correct_sql.prompt`.
- **`execute_sql` is read-only by policy**: the prompts forbid INSERT/UPDATE/DELETE/CREATE. The repository does not enforce this — keep the prompts authoritative.
- **`extract_keywords` POS allowlist**: the `allow_pos` tuple in `extract_keywords.py` (Chinese jieba tags) controls which words reach the recallers. Adding tags changes recall behavior — be deliberate.
- **Request-scoped state**: each request gets a fresh `DataAgentContext` and `DataAgentState`. Do not cache state across requests.

## Tests / verification

Backend unit tests live in `tests/` and use the standard-library `unittest` runner:

- `uv run python -m unittest discover -s tests`

The suite should not require running Compose services. End-to-end verification is done through Compose:

- `make smoke` (runs `scripts/smoke.sh`) — checks frontend root (`/` → 200), `backend /openapi.json` advertises `/api/query`, and `POST /api/query {}` returns `422` (Pydantic validation, not 500).
- `make logs SERVICE=backend` — inspect agent progress events and SQL generation.
- `make logs SERVICE=knowledge-init` — confirm meta knowledge build on first run.

## Code style

- Comments and docstrings inside `app/` are in Chinese; preserve them. New agent nodes should follow the existing pattern: `runtime.stream_writer` progress → `try/except` → `logger.info` on success → `raise` on failure.
- No formatter/linter wired in. Match the surrounding style: 4-space indent, type hints via `TypedDict` / `from __future__ import annotations` is not used — keep Python 3.11 idioms.
- Do not introduce `__init__.py` inside `app/`.
- Do not commit `app_config.yaml`, `__pycache__`, `.venv`, or `*.log`.

## Local native workflow (no Compose)

1. `cp app/core/config/app_config.example.yaml app/core/config/app_config.yaml` and edit host/port/passwords.
2. Have MySQL/ES/Qdrant/embeddings running locally; the embeddings container exposes `BAAI/bge-large-zh-v1.5` on port 80 (change `app_config.embedding.port` to 8081 for native).
3. `uv sync`.
4. Seed MySQL with `infra/docker/mysql/init.sql`.
5. `uv run python -m scripts.wait_and_build_meta` once.
6. `uv run uvicorn app.main:app --reload`. Frontend proxies to `localhost:8000` by default (`API_BASE_URL`).

# AGENTS.md

Agent guidance for the `data-agent` (掌柜问数) repository — shared across coding agents (Claude Code, Codex, etc.). The depth for each module lives in its own `AGENTS.md`; this file is the orientation layer.

## Project overview

`data-agent` is a natural-language → SQL web app. Users type questions; a LangGraph agent retrieves schema from MySQL/Qdrant/Elasticsearch, filters with an LLM, generates and validates SQL against a DW MySQL, and streams the result table back as SSE. The frontend is a single chat page.

The repo follows `docs/ARCHITECTURE_INSTRUCTIONS.md` (reorganization reference; do not invent new top-level directories).

## Service topology

Compose services are defined in `docker-compose.yml`; the `dev` and `prod` profiles select the matching frontend. One shared `backend-environment` YAML anchor feeds both `knowledge-init` and `backend`.

| Service        | Image / build                                 | Host port | Notes                                                                                       |
| -------------- | --------------------------------------------- | --------- | ------------------------------------------------------------------------------------------- |
| `mysql`        | `mysql:8.4`                                   | (internal)| Creates `meta` + `dw` databases from `infra/docker/mysql/init.sql`. Healthchecked.          |
| `elasticsearch`| `docker.elastic.co/elasticsearch/elasticsearch:8.19.3` | (internal)| Single-node, security disabled. Holds full-text value index.                                |
| `qdrant`       | `qdrant/qdrant:v1.16.2`                       | (internal)| Vector store for column & metric embeddings (cosine, dim 1024).                             |
| `embeddings`   | `ghcr.io/huggingface/text-embeddings-inference:cpu-arm64-1.9` | (internal)| Serves `BAAI/bge-large-zh-v1.5`. Model cached in `embedding_model_cache` volume.            |
| `knowledge-init` | `./backend/Dockerfile` (restart: no)        | (one-shot)| Waits for deps, then runs `scripts.wait_and_build_meta`. Skipped if `/state/ready` exists.  |
| `backend`      | `./backend/Dockerfile`                        | 8000      | FastAPI + uvicorn. Starts only after MySQL healthy **and** `knowledge-init` succeeded.     |
| `frontend`     | `frontend/Dockerfile` (`production` target, `prod` profile) | 8080 → 3000 | Next.js standalone production image.                        |
| `frontend-dev` | `frontend/Dockerfile` (`dev` target, `dev` profile) | 8080 → 3000 | Next.js dev server; mounts `frontend/` for HMR.              |

External entrypoint: **http://localhost:8080** (frontend). Frontend's `src/app/api/query/route.ts` proxies SSE to `http://backend:8000` (Compose DNS) or `http://localhost:8000` (local dev).

## Repository map

```
backend/   FastAPI + LangGraph agent. See backend/AGENTS.md.
frontend/  Next.js chat page.      See frontend/AGENTS.md.
infra/     Docker Compose assets.
  docker/mysql/init.sql          DW seed data + meta schema (run on first MySQL start).
docs/      Project conventions (ARCHITECTURE_INSTRUCTIONS, COMMIT_INSTRUCTIONS, README_INSTRUCTIONS, AGENT_INSTRUCTIONS).
scripts/   Cross-service tooling. Currently `smoke.sh` for HTTP probes.
docker-compose.yml, Makefile, .env.example, README.md
```

There is intentionally no `tests/`, `components/`, `hooks/`, `middleware/`, `migrations/`, `stores/`, or `utils/` directory yet — they are created only when real content requires them (per `docs/ARCHITECTURE_INSTRUCTIONS.md`).

## Prerequisites

- Docker Desktop (for Compose-driven dev/prod).
- `make` (Makefile is the only command surface at the root).
- For local (non-Docker) backend: **Python 3.11.2 exactly** (pinned in `backend/.python-version`; `pyproject.toml` requires `>=3.11.2,<3.12`).
- For local frontend: Node 22 (matches Dockerfiles).
- A DeepSeek API key (`DEEPSEEK_API_KEY` in `.env`).

## Root vs module commands

The root `Makefile` wraps Docker Compose; module directories expose Python/npm tooling. Use the root for orchestration; drop into a module for native iteration.

| Goal                          | Command (from repo root)                     |
| ----------------------------- | -------------------------------------------- |
| Start dev stack (HMR frontend)| `make dev` (alias: `make up`)                |
| Start prod stack              | `make prod`                                  |
| Stop (keep volumes/containers)| `make stop` (alias: `make down`)             |
| Restart services              | `make restart`                               |
| Service status                | `make ps`                                    |
| Tail logs                     | `make logs [SERVICE=frontend-dev]`            |
| HTTP smoke test (frontend + backend `/api/query`) | `make smoke` (`./scripts/smoke.sh`) |
| Frontend typecheck            | `make typecheck`                             |
| Build prod images             | `make build`                                 |

For native iteration, see `backend/AGENTS.md` (uvicorn, `uv sync`) and `frontend/AGENTS.md` (`npm run dev/build/typecheck`).

## Setup (first run)

1. `cp .env.example .env` and set `DEEPSEEK_API_KEY`.
2. On macOS, `make dev` opens Docker Desktop if its daemon is not running and waits for it to become ready. On other platforms, start Docker Engine first.
3. `make dev` — first run pulls images, downloads the BGE model (~hundreds of MB), and waits for `knowledge-init` to build the meta knowledge base from `backend/app/core/config/meta_config.yaml`. Watch with `make ps` / `make logs`.
4. Open http://localhost:8080.

`make dev` enables the `dev` Compose profile (`frontend-dev`); `make prod` enables `prod` (`frontend`). Both use targets in `frontend/Dockerfile`. The development frontend mounts `./frontend:/app`, uses `WATCHPACK_POLLING=true`, and keeps `node_modules` and `.next` in anonymous volumes.

## Configuration

- **Runtime env**: `.env` (git-ignored). Required: `DEEPSEEK_API_KEY`, `DATA_AGENT_DB_PASSWORD`. Defaults exist for `MYSQL_ROOT_PASSWORD` and `DATA_AGENT_DB_PASSWORD`.
- **Backend YAML**: `backend/app/core/config/app_config.yaml` is tracked and supplies non-secret defaults. Runtime secrets such as the LLM API key should come from `.env` / environment variables. Overrides via `DATA_AGENT_DB_*`, `DATA_AGENT_QDRANT_*`, `DATA_AGENT_EMBEDDING_*`, `DATA_AGENT_ES_*`, `DATA_AGENT_LLM_API_KEY` are applied in `backend/app/core/config/app_config.py`.
- **Meta knowledge source**: `backend/app/core/config/meta_config.yaml` (defines tables, columns, metrics). This is the single source of truth for the metadata knowledge base and is what `knowledge-init` ingests.
- **Frontend backend URL**: `API_BASE_URL` env var (default `http://localhost:8000`; set to `http://backend:8000` inside Compose).

## Cross-cutting conventions

- **Python**: 3.11.2, managed by `uv` (lockfile: `backend/uv.lock`; both `uv sync --frozen` and the Docker build rely on it). PEP 420 namespace packages are in use — `app.*` is the implicit package root; do not add `__init__.py` files inside `app/`.
- **Backend logging**: loguru with per-request `request_id` injected via `contextvars`; see `backend/app/core/log.py` and `backend/app/core/context.py`. Add `request_id_ctx_var.set(...)` (or rely on `app.main` middleware) and call `logger.info(...)` — do not use `print` for diagnostics.
- **Frontend**: TypeScript strict, `noEmit`, Next.js App Router, React 19, React-jsx, module resolution `bundler`. Path alias: none defined. Use `frontend/src/services/query.ts` for backend calls.
- **Secrets**: never commit `.env` or real API keys/passwords. `.gitignore` blocks `.env*`, `.venv`, `node_modules`, `.next`, `*.tsbuildinfo`, `docs/` from root.
- **Chinese surface**: UI strings, prompts, and field/table descriptions are Chinese. Preserve when editing prompts in `backend/app/agent/prompts/*.md`.

## API contract

- `POST /api/query` (Next.js route → backend) accepts `{ "query": string }` and returns `text/event-stream`. Each event is `data: <json>\n\n`. The frontend parser (`frontend/src/services/query.ts`) ignores malformed events silently.
- Event payload shapes (defined in `frontend/src/types/query.ts` and emitted by `backend/app/agent/nodes/*.py`):
  - `{ "type": "progress", "step": string, "status": "running" | "success" | "error" }`
  - `{ "type": "result", "data": Record<string, unknown>[] }`
  - `{ "type": "error", "message": string }`

## Development workflow

1. Edit code in `backend/` or `frontend/` (dev compose hot-reloads frontend; backend uses uvicorn `--reload` only in native dev, not in Compose).
2. After backend changes inside Compose, run `make restart SERVICE=backend` (or recreate the container with `make dev`). HMR is not enabled for the backend container.
3. Use `make smoke` to verify the HTTP path before opening the UI.
4. `make typecheck` validates frontend TypeScript against `.next/dev/types` and `.next/types` — those are generated; `tsconfig.tsbuildinfo` is git-ignored.
5. Add new schema/metrics by editing `meta_config.yaml` and re-running `knowledge-init` (delete the `knowledge_state` volume, or `make down && make dev`).

## Module guides

- [backend/AGENTS.md](backend/AGENTS.md) — stack, layout, agent topology, repositories, configuration.
- [frontend/AGENTS.md](frontend/AGENTS.md) — Next.js app, chat flow, SSE proxy, styles.

# Frontend

The Next.js frontend provides the Chinese chat interface for 掌柜问数. It submits questions through a server-side API proxy, consumes backend SSE events, and renders progress steps, result tables, and errors.

## Stack

| Area | Technology |
| --- | --- |
| Framework | Next.js 16.3.6, App Router |
| UI | React / React DOM 19.3.0 |
| Language | TypeScript 5.9.3; strict mode, relative imports |
| Styling / State | Global CSS; React hooks |
| Tests | Vitest 5.0.2, Testing Library, jsdom, Playwright |
| Deployment | Node 22 Alpine; Next.js standalone output |

Package versions above are resolved in [package-lock.json](package-lock.json); [package.json](package.json) declares the dependency ranges and scripts.

## Local Setup

Use Node **22.22.2+ (22.x)** and npm to match the project's Node 22 runtime and the locked test dependencies. For live queries, run the backend at `http://localhost:8000` or set `API_BASE_URL` to a reachable backend.

From the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). To run the complete stack with Compose instead, use `make dev` from the root and open [http://localhost:8080](http://localhost:8080).

## Commands

Run from `frontend/`:

| Command | Purpose |
| --- | --- |
| `npm ci` | Install dependencies from the lockfile |
| `npm run dev` | Start the development server |
| `npm run build` | Build the production application |
| `npm run start` | Serve a completed production build |
| `npm run typecheck` | Run `tsc --noEmit` |
| `npm test` | Run unit and component tests |
| `npm run test:watch` | Run Vitest in watch mode |
| `npm run test:coverage` | Run tests with V8 coverage gates |
| `npm run test:e2e:install` | Install Chromium for Playwright |
| `npm run test:e2e` | Run the cross-service browser tests |

## Routes and Streaming

| Route | Source | Behavior |
| --- | --- | --- |
| `/` | `src/app/page.tsx` | Server component rendering the client `ChatPage` |
| `POST /api/query` | `src/app/api/query/route.ts` | Node.js route forwarding JSON to the backend and streaming its response |

The browser sends `{ "query": "..." }` to the relative `/api/query` route. The proxy forwards the body and request cancellation signal to `${API_BASE_URL}/api/query`, preserves the upstream status and content type, and passes through the response stream. It disables caching and returns `502 { "message": "后端服务不可用" }` on connection failure.

`src/services/query.ts` exposes `queryStream(query)`, an async generator. It incrementally decodes UTF-8, retains incomplete frames across chunks, accepts LF or CRLF frame separators, and parses one `data:` line per frame. Malformed JSON and payloads outside the event contract are ignored. HTTP failures or a missing response stream throw an error; ending iteration early cancels the reader.

| Event | Payload | UI behavior |
| --- | --- | --- |
| `progress` | `step: string`, `status: "running" \| "success" \| "error"` | Update the named step in the current query's progress bubble |
| `result` | `data: Record<string, unknown>[]` | Append a table; column names come from the first row |
| `error` | `message?: string` | Append an error bubble, with a fallback message |

See [the backend API contract](../backend/README.md#api) for server validation and serialization.

## Environment

| Variable | Usage | Default / Compose value |
| --- | --- | --- |
| `API_BASE_URL` | Server-side backend URL, read by the route handler | `http://localhost:8000` / `http://backend:8000` |
| `WATCHPACK_POLLING` | Set by Compose for the development frontend | `true` in `frontend-dev` |
| `NODE_ENV` | Set by the Docker build targets | `development` / `production` |

The application uses no `NEXT_PUBLIC_*` variables. Configure the backend address on the Next.js server; the browser always calls the relative route.

## Source Structure

```text
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx          # zh-CN document, title, and global stylesheet
│   │   ├── page.tsx            # Chat page entry
│   │   └── api/query/route.ts  # Backend SSE proxy
│   ├── features/chat/ChatPage.tsx
│   ├── services/query.ts      # SSE parsing and event validation
│   ├── styles/style.css       # Chat layout and table styles
│   └── types/query.ts         # Events and discriminated message types
├── tests/                     # Component, SSE parser, and proxy tests
├── Dockerfile                 # dependencies, dev, build, production stages
├── next.config.ts             # Standalone output
├── playwright.config.ts       # Root E2E suite and isolated test servers
├── vitest.config.mts          # Unit tests and coverage gates
├── tsconfig.json
└── package.json
```

## Tests

Vitest uses Node for service/proxy tests and jsdom for the chat component tests. Fetch, environment, and DOM state are isolated between tests. Coverage requires 85% for lines, statements, and functions, and 80% for branches in the configured source scopes.

```bash
npm test -- tests/query.test.ts
npm run test:coverage
```

Playwright runs [../tests/e2e/](../tests/e2e/) with Chromium and starts its own Next.js server on `127.0.0.1:3100` and FastAPI test server on `127.0.0.1:8100`. Install the backend dependencies with `uv sync --frozen` from `backend/` first, then install Chromium and run `npm run test:e2e`. Alternatively, root `make test-install` prepares both modules and Chromium, and `make test` runs every layer.

E2E exercises the browser, proxy, real agent graph, and in-memory SQL execution with deterministic model/retrieval substitutes. Servers are not reused. Avoid running E2E alongside another Next.js process or build that writes `frontend/.next`. Reports are written to `coverage/`, `playwright-report/`, and `test-results/`.

## Development Notes

- `ChatPage` prevents concurrent submissions, ignores Enter during Chinese input composition, and scrolls as messages arrive. Message history lives in React state.
- Keep `src/types/query.ts` and the parser aligned with backend events. Result cells stringify values; null cells display as empty strings.
- Preserve streaming body passthrough in the proxy and its `nodejs` runtime.
- Keep `output: "standalone"` in `next.config.ts`: the production Docker stage runs the generated `server.js` and copies `.next/static`.
- Compose's `frontend-dev` mounts source at `/app` with separate anonymous volumes for `node_modules` and `.next`. Root `make typecheck` requires that container to be running.
- TypeScript includes generated `.next/types` and `.next/dev/types`. `next-env.d.ts` is generated by Next.js.

## Related Documentation

- [Project overview](../README.md) / [中文概览](../README_zh.md)
- [Backend guide](../backend/README.md)
- [Frontend agent guidance](AGENTS.md)

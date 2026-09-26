# frontend/AGENTS.md

Agent guidance for the Next.js frontend.

For repo-wide orientation (Compose topology, env vars, Make targets), see [AGENTS.md](../AGENTS.md).

## Stack

- **Next.js 16.3** (App Router), **React 19.3**, **TypeScript 5.9**.
- **Node 22** (used by both targets in `Dockerfile`).
- `next.config.ts` sets `output: "standalone"` for the production image — keep it that way; the `production` target in `Dockerfile` depends on `.next/standalone/server.js`.
- No CSS framework, no state library, no UI kit. Global stylesheet at `src/styles/style.css`. Pure CSS variables on `:root`, light theme only.
- No path aliases; imports use relative paths (`../../services/query`, `../../types/query`).

## Commands

Run from `frontend/` unless noted.

| Goal                     | Command                         |
| ------------------------ | ------------------------------- |
| Install                  | `npm ci`                        |
| Dev server (hot reload)  | `npm run dev`                   |
| Production build         | `npm run build`                 |
| Start prod server        | `npm run start`                 |
| Type-check               | `npm run typecheck` (`tsc --noEmit`) |

The `dev` Compose profile builds the `dev` target from `Dockerfile` and runs `npm run dev -- --hostname 0.0.0.0` in `frontend-dev`, with the project mounted at `/app` (anonymous volumes for `node_modules` and `.next`) and `WATCHPACK_POLLING=true`. The `prod` profile builds the standalone `production` target for `frontend`.

Repo-root shortcuts: `make dev` (starts the `dev` profile with HMR), `make typecheck` (execs `npm run typecheck` in `frontend-dev`), `make logs SERVICE=frontend-dev`.

## Source layout

```
src/
├── app/
│   ├── layout.tsx                # Root layout: <html lang="zh-CN">, global CSS, metadata title "掌柜问数"
│   ├── page.tsx                  # Renders <ChatPage />
│   └── api/query/route.ts        # POST → SSE proxy to backend (nodejs runtime)
├── features/chat/
│   └── ChatPage.tsx              # "use client" component, chat UI + message state
├── services/
│   └── query.ts                  # queryStream(query) — async generator over SSE
├── styles/
│   └── style.css                 # Global CSS
└── types/
    └── query.ts                  # QueryEvent, ChatMessage, StepStatus
Dockerfile                        # Shared multi-stage image: dev and production targets
next.config.ts                    # output: "standalone"
tsconfig.json                     # strict, noEmit, jsx: "react-jsx"
```

## Request flow

1. User submits a question in `ChatPage` (`src/features/chat/ChatPage.tsx`). It is appended to `messages` as a `user` text bubble and a placeholder `assistant` `steps` bubble is added.
2. `queryStream(query)` (`src/services/query.ts`) POSTs `{ query }` to **relative** `/api/query`. It reads `response.body` with `getReader()` and yields parsed `QueryEvent`s from the SSE stream. Malformed events are ignored silently.
3. The Next.js route handler (`src/app/api/query/route.ts`) forwards the request to `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api/query`, copying headers (Content-Type, Cache-Control), status, and body. `cache: "no-store"` and `signal: request.signal` preserve client disconnects. On network error it returns `502 { message: "后端服务不可用" }`.
4. As events arrive, `ChatPage` updates the `steps` bubble (`progress`), appends a `table` bubble on `result`, or appends an `error` bubble.

### Event shapes (`src/types/query.ts`)

- `QueryEvent` = `{type: "progress", step, status: "running"|"success"|"error"}` | `{type: "result", data: Record<string, unknown>[]}` | `{type: "error", message?}`
- `ChatMessage` is a discriminated union: `{role: "user", type: "text"}`, `{role: "assistant", type: "steps"}`, `{role: "assistant", type: "table"}`, `{role: "assistant", type: "error"}`. The component narrows on `message.type`.

### Single in-flight guard

`ChatPage` uses a `busy` ref to drop double-submits and disables the Send button while `loading` is true. The `Enter` keypress triggers `sendQuestion()`.

## Configuration & environment

- `API_BASE_URL` (server-side env): default `http://localhost:8000`. Set to `http://backend:8000` inside Compose (`docker-compose.yml`). Read inside the route handler only — do not embed in client bundles.
- No `NEXT_PUBLIC_*` env vars are currently used.
- `next.config.ts`: only `output: "standalone"`. No rewrites, no images config, no env mapping.

## Important invariants

- **SSE proxy must stay server-side**: `src/app/api/query/route.ts` uses `export const runtime = "nodejs"` (not `edge`) — `fetch` streaming with `signal` forwarding and SSE is required.
- **`response.body` passthrough**: the route returns `new Response(upstream.body, ...)` to preserve chunked encoding. Do not buffer.
- **SSE parsing is line-based**: `queryStream` splits on `\r?\n\r?\n` for events and `startsWith("data:")` for payloads. Malformed events are ignored (`catch {}`) — keep this resilient against backend hiccups.
- **Strict mode**: `tsconfig.json` has `"strict": true`, `"noEmit": true`. Type errors block `tsc --noEmit`; `npm run build` will also fail. Generated types from Next.js live under `.next/types/**/*.ts` and `.next/dev/types/**/*.ts` (both git-ignored).
- **No path aliases**: stick with relative imports.
- **CSS classes** for layout: `.chat-page`, `.message-row`, `.bubble`, `.avatar`, `.steps`, `.step`, `.dot`, `.table-wrap`, `.result-table`, `.input-wrapper`, `.input-box`. The stylesheet is the single source of styling truth.

## Tests / verification

There is no test suite. Use:

- `npm run typecheck` for type safety.
- `make smoke` from repo root for the end-to-end HTTP probe (frontend root, backend `/openapi.json`, and a malformed `POST /api/query` returning `422`).
- Manual: open http://localhost:8080 and send a question; the agent step dots should progress through running → success/error, then a result table renders.

## Code style

- React function components only. `ChatPage` is `"use client"` — keep the chat interactivity client-side; `app/page.tsx` and `app/layout.tsx` stay server components.
- Hooks in dependency arrays matter — `useEffect` for scroll-to-bottom uses `[messages]` so it fires on every chat update.
- Use `void` prefix for fire-and-forget async calls in event handlers (`onKeyDown`, `onClick`).
- Keep `src/types/query.ts` in lockstep with the backend SSE contract (`backend/app/services/query_service.py` and `app/agent/nodes/*.py`).

## Local native workflow (no Compose)

1. `npm ci`.
2. Have the backend running (default `localhost:8000`) or set `API_BASE_URL` for a remote host.
3. `npm run dev` → http://localhost:3000 (frontend dev port). Note that `next.config.ts` does not rewrite `/api/query`; the route is served by Next.js itself.

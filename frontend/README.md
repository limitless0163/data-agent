# 前端

TypeScript + React + Next.js 页面。运行 `npm ci && npm run dev` 启动开发服务器，访问 <http://localhost:3000>；运行 `npm run typecheck && npm run build` 验证并构建。`src/app/api/query/route.ts` 将流式请求转发到 FastAPI，默认地址为 `http://localhost:8000`，可通过 `API_BASE_URL` 覆盖。Docker Compose 对外保持 <http://localhost:8080>。

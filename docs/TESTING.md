# 自动化测试

## 安装与运行

本地需要 Python **3.11.2**、uv、Node **22.22.2 或更高的 22.x**、npm 和 make。测试工具的最低 Node 要求高于早期 Node 22；CI 使用最新 Node 22。依赖由 `backend/uv.lock` 和 `frontend/package-lock.json` 锁定。

```sh
make test-install      # 首次安装 Python/npm 开发依赖和 Chromium
make test              # 一键：后端、前端类型检查与测试、跨端 E2E
make test-coverage     # 同一套测试 + 覆盖率门禁与 HTML/XML/LCOV 报告
```

不需要 Docker、`.env`、DeepSeek Key 或任何运行中的数据库/检索服务。首次安装需要下载包及 Chromium；后续测试使用本地依赖。Linux 若缺少浏览器系统库，运行 `cd frontend && npx playwright install --with-deps chromium`。

| 范围 | 根目录命令 | 模块内命令 |
| --- | --- | --- |
| 后端全部 | `make test-backend` | `cd backend && uv run --frozen pytest` |
| 后端指定文件 | — | `cd backend && uv run --frozen pytest tests/test_database.py` |
| 前端类型检查与测试 | `make test-frontend` | `cd frontend && npm run typecheck && npm test` |
| 前端指定文件 | — | `cd frontend && npm test -- tests/query.test.ts` |
| 前端监听 | — | `cd frontend && npm run test:watch` |
| 前端覆盖率 | — | `cd frontend && npm run test:coverage` |
| 跨端全部 | `make test-e2e` | `cd frontend && npm run test:e2e` |
| 跨端指定场景 | — | `cd frontend && npm run test:e2e -- --grep 'model failure'` |

Playwright 自动启动并停止独立 FastAPI（`127.0.0.1:8100`）和 Next.js（`127.0.0.1:3100`）进程；端口已占用时失败，不复用未知服务。Next.js 使用当前源码的开发服务，生产构建另由 CI 验证。不要同时启动多份 E2E，也不要让本地 Next 开发/构建进程并发操作同一 `frontend/.next`。

执行顺序隔离审计：

```sh
cd backend && uv run --frozen pytest --randomly-seed=2026
cd frontend && npm test -- --sequence.shuffle --sequence.seed=2026
```

## 现状与工具选择

建立体系前，后端有 11 个标准库 `unittest` 测试，覆盖图节点注册、MySQL/ES/Qdrant 客户端初始化/关闭、LLM 缓存及并发日志上下文；前端只有 `tsc`，跨端只有依赖 Compose 的 `scripts/smoke.sh`，无测试 CI 和覆盖率。

后端统一使用 `pytest` + FastAPI `TestClient`；`pytest-asyncio` 执行异步测试，`pytest-mock` 管理自动恢复的 Mock，`pytest-cov` 统计执行覆盖，`pytest-randomly` 检查执行顺序隔离。`aiosqlite` 提供真实事务/ORM 集成测试。已迁移原有断言与用例，移除自定义 runner。前端采用 Vitest + Testing Library + jsdom；代理与 SSE 测试在 Node 环境中使用真实 Web Streams。Playwright 承担浏览器和跨服务流程，不重复前端单元职责。

| 测试位置 | 核心覆盖 |
| --- | --- |
| `backend/tests/test_query_api.py` | FastAPI 验证、非法 JSON/类型、405、OpenAPI、依赖覆盖、并发请求 ID、SSE 中文/Decimal 序列化、部分进度后失败、取消传播 |
| `backend/tests/test_agent_graph.py`、`test_agent_nodes.py` | 真实 LangGraph 执行、并行召回后合流、去重、指标字段/取值/主外键补充、真实提示词与输出解析、过滤、SQL 生成/EXPLAIN/校正/执行、模型/检索/DB 异常 |
| `backend/tests/test_database.py`、`test_repositories.py` | ORM 与 JSON 持久化、关系映射、重复写入回滚、参数绑定、真实 SQL 聚合/空结果、MySQL 专属语句调用契约、Qdrant 内存往返/批次、ES mapping/search/bulk 失败 |
| `backend/tests/test_metadata.py` | YAML 构建入口、Decimal 示例转换、同步列选择、指标关联、向量批次及 payload 对齐、空配置和依赖失败 |
| `backend/tests/test_dependencies.py`、`test_config.py` | session 清理、依赖传递、正常/异常/部分启动后客户端清理、环境覆盖/密钥优先级/非法端口 |
| `frontend/tests/chat.test.tsx` | 表单、组件内部 Hooks/状态、点击/回车、重复提交、中文 IME、纯空白输入、步骤更新、空结果、表格零值/null/布尔值、错误重试和滚动 |
| `frontend/tests/query.test.ts`、`route.test.ts` | SSE 分片/中文 UTF-8/CRLF、无效事件、网络/HTTP/读取异常、流取消/锁释放、代理 body/signal/status/header 透传和 502 |
| `tests/e2e/chat.spec.ts` | 浏览器 → Next 代理 → FastAPI → QueryService → 真实 Agent 图 → 内存 SQL → 表格；SQL 校正、空结果、模型异常后恢复、422/SSE 协议、并发隔离、HTTP 失败重试 |

项目没有自定义 Hooks、全局状态库、桌面主进程/IPC 或鉴权模块；测试覆盖实际组件状态、HTTP/SSE 通信和依赖注入，不为不存在的模块造测试。

## 隔离与生命周期

- 后端 `tests/conftest.py` 在测试收集前屏蔽 `.env`、服务环境覆盖和文件/控制台日志，设置虚拟 LLM key。每个测试自动启用 socket 连接保护、清理 LLM 缓存及请求上下文；会话结束恢复环境并删除临时 jieba 目录。
- API fixture 用 `with TestClient(app)` 执行真实生产 lifespan，将外部客户端替换为 Mock；退出 TestClient 后验证客户端 init/close，应用依赖由 monkeypatch 自动恢复。并发 API 用例在独立线程中发起请求。
- 每个数据库集成用例、每次 E2E 请求均使用新的 `sqlite+aiosqlite:///:memory:` 引擎，session 和引擎通过 cleanup / `finally` 关闭，不读取生产 DSN，不使用 Compose 数据卷。
- Qdrant 集成使用 `:memory:` 客户端并关闭；ES、embedding 和 LLM 使用本地 Mock/Runnable。图、提示词、解析器、路由和序列化代码仍然执行。
- 后端 `mocker` / `monkeypatch`、环境覆盖、API dependency overrides、LLM 缓存均在用例结束时恢复/清空；元数据 YAML 使用 `TemporaryDirectory`，jieba 缓存写入测试临时目录并在退出时清理。
- Vitest 自动恢复 Mock、全局变量和环境变量；Testing Library 每个测试卸载组件。异步交互通过事件/Promise gate 同步，不依赖固定 sleep 或执行顺序。
- Playwright 每个场景使用新 browser context；额外 context 在 `finally` 关闭。测试后停止服务并释放内存数据库；仅失败时保存截图/trace。后端 E2E 连接限制在 loopback，真实外部服务不可达。
- `coverage/`、`htmlcov/`、`coverage.xml`、`.coverage*`、`playwright-report/`、`test-results/` 是有意保留的诊断产物，已加入忽略规则并从 Docker build context 排除。

## 覆盖率与 CI

`backend/htmlcov/index.html`、`backend/coverage.xml`、`frontend/coverage/index.html`、`frontend/coverage/lcov.info` 为报告。后端统计 `app/` 的语句及分支，门禁为合并覆盖率 **80%**；前端统计聊天组件、SSE service 和 API proxy，门禁为语句/行/函数 **85%**、分支 **80%**。样式、静态布局与类型声明由浏览器/类型检查补充。

覆盖率仅表示哪些代码执行过，Mock 环境的高覆盖率不证明真实模型回答正确，也不证明真实 MySQL/ES 的行为。

`.github/workflows/tests.yml` 在 push/PR 自动安装锁定依赖和 Chromium，运行 `make test-coverage`、生产前端构建；失败即阻断 job，保存覆盖率与浏览器诊断 7 天。CI 不需要密钥或外部服务。要在 GitHub 阻止失败 PR 合并，还需仓库管理员将 `Tests / tests` 设置为分支保护必需检查。

工具参考：[pytest fixture](https://docs.pytest.org/en/stable/how-to/fixtures.html)、[FastAPI TestClient 生命周期](https://fastapi.tiangolo.com/advanced/testing-events/)、[Vitest coverage](https://vitest.dev/guide/coverage)、[Testing Library](https://testing-library.com/docs/react-testing-library/setup/)、[Playwright 多服务管理](https://playwright.dev/docs/test-webserver)。

## 仍需后续验证的风险

| 风险/未覆盖内容 | 原因与后续建议 |
| --- | --- |
| MySQL 8.4 专有方言、collation、锁/连接池、asyncmy JSON/Decimal 行为 | SQLite 验证通用 SQL/事务；MySQL 专属语句目前验证调用契约。后续增加独立临时 MySQL 容器的可选 CI job，专用凭据和数据库，退出销毁，不复用开发卷。 |
| ES 8.x 中文分词/相关性、真实 Qdrant/embedding 召回质量 | 内存 Qdrant/Mock 无法代表部署服务与中文语料。增加版本匹配的临时服务及固定小语料集成任务。 |
| DeepSeek SQL 语义、幻觉、提示词注入 | 默认测试使用确定性模型，不依赖联网输出。建立固定问句/期望结果评测，真实模型评测单独运行，避免将概率性输出变成普通 PR 的脆弱门禁。 |
| 鉴权与数据库只读保障 | 项目尚无鉴权；SQL 只读目前依赖提示词，初始化 SQL 给 DW 用户 ALL PRIVILEGES。测试不虚构安全保证。后续明确访问模型、DW 只读凭据和 SQL 执行策略后补专项测试。 |
| knowledge-init 多存储部分失败后的重跑/幂等与服务等待脚本 | MySQL/ES/Qdrant 之间无跨存储事务，当前测试检查构建失败传播，未验证完整 Compose 初始化/标记生命周期。用隔离 Compose 项目和临时卷验证恢复。 |
| 大结果集、真实断连/代理背压、慢服务、负载与浏览器差异 | 已覆盖单元取消、signal 透传和并发功能隔离，未做负载/真实网络故障测试；默认浏览器仅 Chromium。后续按部署规模增压测和 Firefox/WebKit。 |
| 空结果 UI 与非法模型输出的语义形状 | 空结果保持现有空表行为；测试保证不崩溃。模型 JSON 解析错误已覆盖，但不保证所有合法错误形状的业务校验，后续可增加显式模型输出 schema 与用户空态。 |
| 日志文件轮转、生产容器与部署初始化 | 测试关闭文件日志，应用 lifespan 的外部客户端由 Mock 替换；生产前端仅构建验证。继续用 `make smoke` 对隔离的部署栈探活。 |

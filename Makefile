.DEFAULT_GOAL := help

COMPOSE := docker compose
DEV_COMPOSE := $(COMPOSE) --profile dev
PROD_COMPOSE := $(COMPOSE) --profile prod
ALL_COMPOSE := $(COMPOSE) --profile dev --profile prod
SERVICE ?=

.PHONY: help docker-ready dev up prod stop down restart ps logs smoke typecheck build

help:
	@printf '%s\n' \
		'make dev        启动完整开发环境（前端热更新），macOS 会按需启动 Docker Desktop' \
		'make up         与 make dev 相同' \
		'make prod       使用生产镜像启动完整环境' \
		'make stop       停止服务，保留容器和数据卷' \
		'make down       与 make stop 相同' \
		'make restart    重启开发环境中的服务' \
		'make ps         查看服务状态' \
		'make logs       跟踪开发环境日志；可指定 SERVICE=frontend-dev 等服务名' \
		'make smoke      检查前后端 HTTP 接口' \
		'make typecheck  检查前端 TypeScript 类型（需先 make dev）' \
		'make build      构建生产镜像'

dev: docker-ready
	$(PROD_COMPOSE) stop frontend
	$(DEV_COMPOSE) up --build --detach --renew-anon-volumes
	@printf '%s\n' '开发环境已启动： http://localhost:8080' '首次启动需要等待镜像、向量模型和元知识库初始化；可运行 make ps 或 make logs 查看进度。'

up: dev

prod: docker-ready
	$(DEV_COMPOSE) stop frontend-dev
	$(PROD_COMPOSE) up --build --detach
	@printf '%s\n' '生产环境已启动： http://localhost:8080'

docker-ready:
	@if ! command -v docker >/dev/null 2>&1; then \
		printf '%s\n' '未找到 docker 命令，请先安装 Docker Desktop 或 Docker Engine。' >&2; \
		exit 1; \
	fi
	@if docker info >/dev/null 2>&1; then \
		:; \
	elif [ "$$(uname -s)" = Darwin ]; then \
		printf '%s\n' 'Docker daemon 未运行，正在打开 Docker Desktop 并等待就绪（最长 180 秒）...'; \
		if ! open -a Docker; then \
			printf '%s\n' '无法打开 Docker Desktop，请确认已安装。' >&2; \
			exit 1; \
		fi; \
		attempt=0; \
		until docker info >/dev/null 2>&1; do \
			if [ $$attempt -ge 90 ]; then \
				printf '%s\n' '等待 Docker Desktop 超时，请检查 Docker Desktop 是否正常启动。' >&2; \
				exit 1; \
			fi; \
			sleep 2; \
			attempt=$$((attempt + 1)); \
		done; \
		printf '%s\n' 'Docker Desktop 已就绪。'; \
	else \
		printf '%s\n' 'Docker daemon 未运行，请先启动 Docker Engine。' >&2; \
		exit 1; \
	fi

stop:
	$(ALL_COMPOSE) stop

down: stop

restart:
	$(DEV_COMPOSE) restart

ps:
	$(DEV_COMPOSE) ps

logs:
	$(DEV_COMPOSE) logs --follow --tail=100 $(SERVICE)

smoke:
	./scripts/smoke.sh

typecheck:
	$(DEV_COMPOSE) exec frontend-dev npm run typecheck

build:
	$(PROD_COMPOSE) build

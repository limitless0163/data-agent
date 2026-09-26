.DEFAULT_GOAL := help

COMPOSE := docker compose -f docker-compose.yml
DEV_COMPOSE := $(COMPOSE) -f docker-compose.dev.yml
SERVICE ?=

.PHONY: help dev up prod stop down restart ps logs smoke typecheck build

help:
	@printf '%s\n' \
		'make dev        启动完整开发环境（前端热更新），访问 http://localhost:8080' \
		'make up         与 make dev 相同' \
		'make prod       使用生产镜像启动完整环境' \
		'make stop       停止服务，保留容器和数据卷' \
		'make down       与 make stop 相同' \
		'make restart    重启开发环境中的服务' \
		'make ps         查看服务状态' \
		'make logs       跟踪日志；可指定 SERVICE=frontend 等服务名' \
		'make smoke      检查前后端 HTTP 接口' \
		'make typecheck  检查前端 TypeScript 类型（需先 make dev）' \
		'make build      构建生产镜像'

dev:
	$(DEV_COMPOSE) up --build --detach --renew-anon-volumes
	@printf '%s\n' '开发环境已启动： http://localhost:8080' '首次启动需要等待镜像、向量模型和元知识库初始化；可运行 make ps 或 make logs 查看进度。'

up: dev

prod:
	$(COMPOSE) up --build --detach
	@printf '%s\n' '生产环境已启动： http://localhost:8080'

stop:
	$(DEV_COMPOSE) stop

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
	$(DEV_COMPOSE) exec frontend npm run typecheck

build:
	$(COMPOSE) build

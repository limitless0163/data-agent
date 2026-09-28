import uuid

from fastapi import FastAPI, Request

from app.api.routers.query_router import query_router
from app.core.context import request_id_ctx_var
from app.core.lifespan import lifespan

app = FastAPI(lifespan=lifespan)

app.include_router(query_router)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """为请求上下文注入唯一标识，关联该请求的节点日志。"""
    request_id_ctx_var.set(uuid.uuid4())

    response = await call_next(request)

    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

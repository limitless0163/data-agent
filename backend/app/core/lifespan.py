from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI

from app.core.clients.embedding_client_manager import embedding_client_manager
from app.db.es_client_manager import es_client_manager
from app.db.mysql_client_manager import (
    dw_mysql_client_manager,
    meta_mysql_client_manager,
)
from app.db.qdrant_client_manager import qdrant_client_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 每个成功初始化的客户端立即注册清理，启动或关闭失败也不泄漏资源。
    async with AsyncExitStack() as stack:
        embedding_client_manager.init()
        for manager in (
            qdrant_client_manager,
            es_client_manager,
            meta_mysql_client_manager,
            dw_mysql_client_manager,
        ):
            manager.init()
            stack.push_async_callback(manager.close)
        yield

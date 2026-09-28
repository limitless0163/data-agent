from app.core.config.app_config import QdrantConfig, app_config
from qdrant_client import AsyncQdrantClient


class QdrantClientManager:
    def __init__(self, qdrant_config: QdrantConfig):
        self.qdrant_config = qdrant_config
        self.client: AsyncQdrantClient | None = None

    def _get_url(self):
        return f"http://{self.qdrant_config.host}:{self.qdrant_config.port}"

    def init(self):
        self.client = AsyncQdrantClient(url=self._get_url())

    async def close(self):
        await self.client.close()


qdrant_client_manager = QdrantClientManager(app_config.qdrant)

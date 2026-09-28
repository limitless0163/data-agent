from dataclasses import asdict

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config.app_config import app_config
from app.entities.metric_info import MetricInfo


class MetricQdrantRepository:
    collection_name = "data-agent-metric"

    def __init__(self, client: AsyncQdrantClient):
        self.client = client

    async def ensure_collection(self):
        if not await self.client.collection_exists(self.collection_name):
            await self.client.create_collection(
                self.collection_name,
                vectors_config=VectorParams(
                    size=app_config.qdrant.embedding_size, distance=Distance.COSINE
                ),
            )

    async def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        payloads: list[MetricInfo],
        batch_size: int = 20,
    ):
        """分批写入向量；三组列表须等长，且相同下标对应同一条记录。"""
        zipped = list(zip(ids, embeddings, payloads))
        for i in range(0, len(zipped), batch_size):
            batch = zipped[i : i + batch_size]
            batch_points = [
                PointStruct(id=id, vector=embedding, payload=asdict(payload))
                for id, embedding, payload in batch
            ]
            await self.client.upsert(
                collection_name=self.collection_name, points=batch_points
            )

    async def search(
        self, embedding: list[float], score_threshold: float = 0.6, limit: int = 5
    ) -> list[MetricInfo]:
        """按余弦相似度返回候选指标；阈值为相似度下限，尚未按实体去重。"""
        result = await self.client.query_points(
            collection_name=self.collection_name,
            query=embedding,
            score_threshold=score_threshold,
            limit=limit,
        )
        return [MetricInfo(**point.payload) for point in result.points]

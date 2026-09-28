from dataclasses import asdict
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.config.app_config import app_config
from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.value_info import ValueInfo
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


def column(name="amount", role="measure"):
    return ColumnInfo(
        f"orders.{name}", name, "decimal", role, [1], "金额", ["销售额"], "orders"
    )


def metric():
    return MetricInfo("GMV", "GMV", "成交额", ["orders.amount"], ["销售额"])


class TestDWRepository:
    @pytest.fixture(autouse=True)
    def setup(self, mocker):
        self.session = mocker.Mock(execute=mocker.AsyncMock(return_value=mocker.Mock()))
        self.repo = DWMySQLRepository(self.session)

    async def test_column_metadata_values_and_database_dialect(self):
        result = self.session.execute.return_value
        result.fetchall.return_value = [
            SimpleNamespace(Field="amount", Type="decimal(10,2)")
        ]
        assert await self.repo.get_column_types("orders") == {"amount": "decimal(10,2)"}
        assert str(self.session.execute.call_args.args[0]) == "show columns from orders"
        result.scalars.return_value.fetchall.return_value = [Decimal("1.2"), None]
        assert await self.repo.get_column_values("orders", "amount", 10) == [
            Decimal("1.2"),
            None,
        ]
        assert (
            str(self.session.execute.call_args.args[0])
            == "select distinct amount from orders limit 10"
        )
        result.scalar.return_value = "8.4"
        self.session.get_bind.return_value.dialect.name = "mysql"
        assert await self.repo.get_db_info() == {"version": "8.4", "dialect": "mysql"}

    async def test_explain_and_result_mapping_preserve_decimal_and_empty_results(self):
        await self.repo.validate_sql("select amount from orders")
        assert (
            str(self.session.execute.call_args.args[0])
            == "explain select amount from orders"
        )
        self.session.execute.return_value.mappings.return_value.fetchall.return_value = [
            {"amount": Decimal("1.2")}
        ]
        assert await self.repo.execute_sql("select amount from orders") == [
            {"amount": Decimal("1.2")}
        ]
        self.session.execute.return_value.mappings.return_value.fetchall.return_value = []
        assert await self.repo.execute_sql("select amount from orders where 1=0") == []

    async def test_database_failure_propagates(self):
        self.session.execute.side_effect = SQLAlchemyError("bad sql")
        for call in [self.repo.validate_sql, self.repo.execute_sql]:
            with pytest.raises(SQLAlchemyError):
                await call("select missing")


class TestQdrantRepository:
    @pytest.mark.parametrize(
        "repo_type", [ColumnQdrantRepository, MetricQdrantRepository]
    )
    async def test_collection_creation_is_idempotent_and_preserves_dimension(
        self, mocker, repo_type
    ):
        client = mocker.Mock(
            collection_exists=mocker.AsyncMock(return_value=False),
            create_collection=mocker.AsyncMock(),
        )
        repo = repo_type(client)
        await repo.ensure_collection()
        params = client.create_collection.call_args.kwargs["vectors_config"]
        assert params.size == app_config.qdrant.embedding_size
        assert params.distance.value == "Cosine"
        client.collection_exists.return_value = True
        await repo.ensure_collection()
        assert client.create_collection.await_count == 1

    @pytest.mark.parametrize(
        "repo_type,payload",
        [(ColumnQdrantRepository, column()), (MetricQdrantRepository, metric())],
    )
    async def test_batches_payloads_searches_and_empty_upserts(
        self, mocker, repo_type, payload
    ):
        client = mocker.Mock(upsert=mocker.AsyncMock(), query_points=mocker.AsyncMock())
        repo = repo_type(client)
        ids = [str(uuid4()) for _ in range(3)]
        await repo.upsert(ids, [[1.0]] * 3, [payload] * 3, batch_size=2)
        assert [
            len(call.kwargs["points"]) for call in client.upsert.call_args_list
        ] == [2, 1]
        assert client.upsert.call_args_list[0].kwargs["points"][0].payload == asdict(
            payload
        )
        client.query_points.return_value = SimpleNamespace(
            points=[SimpleNamespace(payload=asdict(payload))]
        )
        assert await repo.search([1.0], score_threshold=0.8, limit=2) == [payload]
        client.query_points.assert_awaited_once_with(
            collection_name=repo.collection_name,
            query=[1.0],
            score_threshold=0.8,
            limit=2,
        )
        client.upsert.reset_mock()
        await repo.upsert([], [], [])
        client.upsert.assert_not_awaited()

    async def test_local_qdrant_vector_round_trip_without_network(self, qdrant_client):
        client = qdrant_client
        repo = ColumnQdrantRepository(client)
        await repo.ensure_collection()
        vector = [1.0] + [0.0] * (app_config.qdrant.embedding_size - 1)
        await repo.upsert([str(uuid4())], [vector], [column()])
        assert await repo.search(vector) == [column()]


class TestESRepository:
    async def test_index_creation_batching_and_search_mapping(self, mocker):
        client = mocker.Mock(
            indices=mocker.Mock(
                exists=mocker.AsyncMock(return_value=False), create=mocker.AsyncMock()
            ),
            bulk=mocker.AsyncMock(return_value={"errors": False}),
            search=mocker.AsyncMock(),
        )
        repo = ValueESRepository(client)
        await repo.ensure_index()
        client.indices.create.assert_awaited_once_with(
            index=repo.index_name, mappings=repo.index_mappings
        )
        client.indices.exists.return_value = True
        await repo.ensure_index()
        assert client.indices.create.await_count == 1
        values = [ValueInfo(str(i), f"华东{i}", "regions.name") for i in range(3)]
        await repo.index(values, batch_size=2)
        assert [
            len(call.kwargs["operations"]) for call in client.bulk.call_args_list
        ] == [4, 2]
        assert client.bulk.call_args_list[0].kwargs["operations"][:2] == [
            {"index": {"_index": repo.index_name, "_id": "0"}},
            asdict(values[0]),
        ]
        client.search.return_value = {
            "hits": {"hits": [{"_source": asdict(values[0])}]}
        }
        assert await repo.search("华东", 1.0, 2) == [values[0]]
        client.search.assert_awaited_once_with(
            index=repo.index_name,
            query={"match": {"value": "华东"}},
            min_score=1.0,
            size=2,
        )
        client.bulk.reset_mock()
        await repo.index([])
        client.bulk.assert_not_awaited()

    async def test_bulk_partial_failure_must_not_silently_mark_build_successful(
        self, mocker
    ):
        client = mocker.Mock(
            bulk=mocker.AsyncMock(
                return_value={
                    "errors": True,
                    "items": [
                        {"index": {"status": 400, "error": {"reason": "invalid value"}}}
                    ],
                }
            )
        )
        with pytest.raises(RuntimeError):
            await ValueESRepository(client).index([ValueInfo("1", "华东", "r.name")])

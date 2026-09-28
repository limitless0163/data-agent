import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.entities.column_info import ColumnInfo
from app.entities.column_metric import ColumnMetric
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.models.base import Base
from app.models.column_metric_mysql import ColumnMetricMySQL
from app.models.metric_info_mysql import MetricInfoMySQL
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository


class TestDatabaseIntegration:
    @pytest.fixture(autouse=True)
    async def database(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with self.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
                await connection.execute(
                    text("create table orders (id integer primary key, amount integer)")
                )
                await connection.execute(
                    text("insert into orders values (1, 20), (2, 30)")
                )
            async with async_sessionmaker(
                self.engine, expire_on_commit=False
            )() as self.session:
                self.repo = MetaMySQLRepository(self.session)
                yield
        finally:
            await self.engine.dispose()

    async def seed(self):
        columns = [
            ColumnInfo(
                "orders.id",
                "id",
                "int",
                "primary_key",
                [1],
                "编号",
                ["订单ID"],
                "orders",
            ),
            ColumnInfo(
                "orders.amount",
                "amount",
                "int",
                "measure",
                [20, 30],
                "金额",
                [],
                "orders",
            ),
            ColumnInfo(
                "orders.customer",
                "customer",
                "int",
                "foreign_key",
                [],
                "客户",
                [],
                "orders",
            ),
        ]
        async with self.session.begin():
            await self.repo.save_table_infos(
                [TableInfo("orders", "orders", "fact", "订单")]
            )
            await self.repo.save_column_infos(columns)
            await self.repo.save_metric_infos(
                [MetricInfo("GMV", "GMV", "成交额", ["orders.amount"], ["销售额"])]
            )
            await self.repo.save_column_metrics([ColumnMetric("orders.amount", "GMV")])
        return columns

    async def test_persisted_entities_json_keys_and_relationships_round_trip(self):
        columns = await self.seed()
        self.session.expunge_all()
        assert (await self.repo.get_table_info_by_id("orders")).description == "订单"
        assert await self.repo.get_column_info_by_id("orders.id") == columns[0]
        assert await self.repo.get_column_info_by_id("missing") is None
        assert await self.repo.get_table_info_by_id("missing") is None
        keys = await self.repo.get_key_columns_by_table_id("orders")
        assert {key.id for key in keys} == {"orders.id", "orders.customer"}
        assert all(
            isinstance(key.examples, list) and isinstance(key.alias, list)
            for key in keys
        )
        model = await self.session.get(MetricInfoMySQL, "GMV")
        assert model.relevant_columns == ["orders.amount"]
        relationship = await self.session.get(
            ColumnMetricMySQL, ("orders.amount", "GMV")
        )
        assert relationship.metric_id == "GMV"

    async def test_duplicate_write_rolls_back_whole_transaction(self):
        with pytest.raises(IntegrityError):
            async with self.session.begin():
                await self.repo.save_table_infos(
                    [
                        TableInfo("same", "one", "fact", ""),
                        TableInfo("same", "two", "fact", ""),
                    ]
                )
        assert await self.repo.get_table_info_by_id("same") is None
        await self.session.rollback()
        async with self.session.begin():
            await self.repo.save_table_infos([TableInfo("ok", "ok", "fact", "")])
        assert await self.repo.get_table_info_by_id("ok") is not None

    async def test_parameterized_table_id_cannot_expand_key_selection(self):
        await self.seed()
        assert await self.repo.get_key_columns_by_table_id("orders' OR 1=1 --") == []

    async def test_dw_real_sql_aggregation_validation_and_error(self):
        repo = DWMySQLRepository(self.session)
        assert await repo.execute_sql("select sum(amount) as total from orders") == [
            {"total": 50}
        ]
        assert await repo.execute_sql("select id from orders where id = 99") == []
        await repo.validate_sql("select id from orders")
        with pytest.raises(SQLAlchemyError):
            await repo.execute_sql("select missing from orders")

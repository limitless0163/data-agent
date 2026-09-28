from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from test_repositories import column, metric

from app.core.config.meta_config import (
    ColumnConfig,
    MetaConfig,
    MetricConfig,
    TableConfig,
)
from app.services.meta_knowledge_service import MetaKnowledgeService


class TestMetaKnowledge:
    @pytest.fixture(autouse=True)
    def setup(self, mocker):
        self.meta = mocker.Mock(
            session=mocker.Mock(begin=mocker.Mock(return_value=mocker.AsyncMock())),
            save_table_infos=mocker.AsyncMock(),
            save_column_infos=mocker.AsyncMock(),
            save_metric_infos=mocker.AsyncMock(),
            save_column_metrics=mocker.AsyncMock(),
        )
        self.dw = mocker.Mock(
            get_column_types=mocker.AsyncMock(return_value={"amount": "decimal"}),
            get_column_values=mocker.AsyncMock(
                return_value=[Decimal("12.30"), None, "华东"]
            ),
        )
        self.columns = mocker.Mock(
            ensure_collection=mocker.AsyncMock(), upsert=mocker.AsyncMock()
        )
        self.values = mocker.Mock(
            ensure_index=mocker.AsyncMock(), index=mocker.AsyncMock()
        )
        self.metrics = mocker.Mock(
            ensure_collection=mocker.AsyncMock(), upsert=mocker.AsyncMock()
        )
        self.embedding = mocker.Mock(
            aembed_documents=mocker.AsyncMock(
                side_effect=lambda texts: [[float(i)] for i in range(len(texts))]
            )
        )
        self.service = MetaKnowledgeService(
            self.meta, self.dw, self.columns, self.embedding, self.values, self.metrics
        )
        self.config = MetaConfig(
            tables=[
                TableConfig(
                    "orders",
                    "fact",
                    "订单",
                    [ColumnConfig("amount", "measure", "金额", ["销售额"], True)],
                )
            ],
            metrics=[MetricConfig("GMV", "成交额", ["orders.amount"], ["销售额"])],
        )

    async def test_table_examples_convert_decimal_before_json_persistence(self):
        result = await self.service._save_tables_to_meta_db(self.config)
        assert result[0].examples == [12.3, None, "华东"]
        assert result[0].id == "orders.amount"
        self.meta.save_column_infos.assert_awaited_once_with(result)
        self.meta.session.begin.return_value.__aexit__.assert_awaited_once()

    async def test_metric_column_relationships_and_embedding_batches(self):
        result = await self.service._save_metrics_to_meta_db(self.config)
        assert result[0].relevant_columns == ["orders.amount"]
        assert (
            self.meta.save_column_metrics.call_args.args[0][0].column_id
            == "orders.amount"
        )
        item = column()
        item.alias = [f"别名{i}" for i in range(21)]
        await self.service._save_column_info_to_qdrant([item])
        assert [
            len(call.args[0]) for call in self.embedding.aembed_documents.call_args_list
        ] == [10, 10, 3]
        ids, vectors, payloads = self.columns.upsert.call_args.args
        assert len(set(ids)) == 23
        assert len(vectors) == 23
        assert payloads == [item] * 23
        self.embedding.aembed_documents.reset_mock()
        await self.service._save_metric_info_to_qdrant([metric()])
        assert self.embedding.aembed_documents.call_args.args[0] == [
            "GMV",
            "成交额",
            "销售额",
        ]

    async def test_only_sync_columns_are_indexed(self):
        self.dw.get_column_values.return_value = ["华东", "华南"]
        await self.service._save_value_info_to_es(self.config, [column()])
        assert [value.value for value in self.values.index.call_args.args[0]] == [
            "华东",
            "华南",
        ]
        self.config.tables[0].columns[0].sync = False
        self.dw.get_column_values.reset_mock()
        await self.service._save_value_info_to_es(self.config, [column()])
        self.dw.get_column_values.assert_not_awaited()
        assert self.values.index.call_args.args[0] == []

    async def test_build_empty_and_complete_config_and_propagates_failure(self):
        with TemporaryDirectory() as directory:
            config = Path(directory) / "meta.yaml"
            config.write_text("tables: []\nmetrics: []\n", encoding="utf-8")
            await self.service.build(config)
            self.meta.save_table_infos.assert_not_awaited()
            config.write_text(
                "tables:\n  - name: orders\n    role: fact\n    description: 订单\n    columns:\n      - name: amount\n        role: measure\n        description: 金额\n        alias: []\n        sync: false\nmetrics:\n  - name: GMV\n    description: 成交额\n    relevant_columns: [orders.amount]\n    alias: []\n",
                encoding="utf-8",
            )
            await self.service.build(config)
            self.columns.upsert.assert_awaited_once()
            self.metrics.upsert.assert_awaited_once()
            self.dw.get_column_types.side_effect = RuntimeError("DW unavailable")
            with pytest.raises(RuntimeError, match="DW unavailable"):
                await self.service.build(config)

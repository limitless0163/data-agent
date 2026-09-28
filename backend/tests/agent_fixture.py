"""Deterministic external collaborators; the production graph and prompts stay real."""

from contextlib import contextmanager
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

from langchain_core.runnables import RunnableLambda
from pytest import MonkeyPatch

from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.entities.value_info import ValueInfo

NODES_WITH_LLM = (
    "recall_column",
    "recall_value",
    "recall_metric",
    "filter_table",
    "filter_metric",
    "generate_sql",
    "correct_sql",
)
SQL = "select region as 地区, sum(amount) as 销售额 from orders where region = '华东' group by region"


def model_response(prompt):
    text = prompt.to_string()
    if "模型故障" in text:
        raise RuntimeError("测试模型不可用")
    if "字段语义检索词生成器" in text:
        return '["金额"]'
    if "字段取值语义检索词生成器" in text:
        return '["华东"]'
    if "指标语义检索词生成器" in text:
        return '["GMV"]'
    if "查询 schema 筛选专家" in text:
        return '{"orders": ["id", "amount", "region"]}'
    if "指标筛选专家" in text:
        return '["GMV"]'
    if "MySQL 查询校正专家" in text:
        return SQL
    if "MySQL 查询生成专家" in text:
        if "测试校正" in text:
            return "select missing from orders"
        if "空结果" in text:
            return "select region as 地区, amount as 销售额 from orders where 1 = 0"
        return SQL
    raise AssertionError("Unexpected prompt")


@contextmanager
def deterministic_model():
    with MonkeyPatch.context() as patches:
        for name in NODES_WITH_LLM:
            module = import_module(f"app.agent.nodes.{name}")
            patches.setattr(module, "get_llm", lambda: RunnableLambda(model_response))
        yield


def collaborators(mocker=None):
    amount = ColumnInfo(
        "orders.amount",
        "amount",
        "decimal",
        "measure",
        [10],
        "金额",
        ["销售额"],
        "orders",
    )
    region = ColumnInfo(
        "orders.region",
        "region",
        "varchar",
        "dimension",
        ["华东"],
        "地区",
        [],
        "orders",
    )
    key = ColumnInfo("orders.id", "id", "int", "primary_key", [1], "编号", [], "orders")
    mapping = {item.id: item for item in [amount, region, key]}

    def dependency(**methods):
        if mocker is not None:
            return mocker.Mock(
                **{
                    name: mocker.AsyncMock(side_effect=value)
                    if callable(value)
                    else mocker.AsyncMock(return_value=value)
                    for name, value in methods.items()
                }
            )

        # E2E runs outside pytest; use simple local async implementations.
        def method(value):
            async def invoke(*args, **kwargs):
                return value(*args, **kwargs) if callable(value) else value

            return invoke

        return SimpleNamespace(
            **{name: method(value) for name, value in methods.items()}
        )

    return {
        "embedding_client": dependency(aembed_query=[1.0]),
        "column_qdrant_repository": dependency(search=[amount]),
        "value_es_repository": dependency(
            search=[ValueInfo("east", "华东", region.id)]
        ),
        "metric_qdrant_repository": dependency(
            search=[MetricInfo("GMV", "GMV", "成交额", [amount.id], [])]
        ),
        "meta_mysql_repository": dependency(
            get_column_info_by_id=mapping.get,
            get_table_info_by_id=TableInfo("orders", "orders", "fact", "订单"),
            get_key_columns_by_table_id=[key],
        ),
        "dw_mysql_repository": dependency(
            get_db_info={"dialect": "mysql", "version": "8.4"},
            validate_sql=None,
            execute_sql=[{"地区": "华东", "销售额": Decimal("30.50")}],
        ),
    }

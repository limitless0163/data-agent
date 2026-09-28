from copy import deepcopy
from datetime import UTC
from importlib import import_module
from types import SimpleNamespace

import pytest
from langchain_core.exceptions import OutputParserException
from langchain_core.runnables import RunnableLambda
from sqlalchemy.exc import SQLAlchemyError
from test_repositories import column, metric

from app.agent.nodes.execute_sql import execute_sql
from app.agent.nodes.extract_keywords import extract_keywords
from app.agent.nodes.merge_retrieved_info import merge_retrieved_info
from app.agent.nodes.validate_sql import validate_sql
from app.entities.table_info import TableInfo
from app.entities.value_info import ValueInfo


def runtime(**deps):
    events = []
    return (SimpleNamespace(context=deps, stream_writer=events.append), events)


def state():
    return {
        "query": "华东销售额",
        "keywords": ["华东"],
        "table_infos": [
            {
                "name": "orders",
                "role": "fact",
                "description": "订单",
                "columns": [{"name": "amount"}, {"name": "id"}],
            }
        ],
        "metric_infos": [{"name": "GMV"}, {"name": "AOV"}],
        "date_info": {"date": "2026-09-28", "weekday": "Monday", "quarter": "Q3"},
        "db_info": {"dialect": "mysql", "version": "8.4"},
        "sql": "select missing",
        "error": "unknown column",
    }


class TestAgentNode:
    async def test_merge_deduplicates_recalled_data_and_adds_metric_columns_values_and_keys(
        self, mocker
    ):
        amount = column()
        key = column("id", "primary_key")
        repository = mocker.Mock(
            get_column_info_by_id=mocker.AsyncMock(return_value=amount),
            get_key_columns_by_table_id=mocker.AsyncMock(return_value=[key]),
            get_table_info_by_id=mocker.AsyncMock(
                return_value=TableInfo("orders", "orders", "fact", "订单")
            ),
        )
        rt, events = runtime(meta_mysql_repository=repository)
        result = await merge_retrieved_info(
            {
                "retrieved_columns": [],
                "retrieved_values": [
                    ValueInfo("v1", 2, amount.id),
                    ValueInfo("v1", 2, amount.id),
                ],
                "retrieved_metrics": [metric()],
            },
            rt,
        )
        repository.get_column_info_by_id.assert_awaited_once_with("orders.amount")
        assert result["table_infos"][0]["columns"][0]["examples"] == [1, 2]
        assert [item["name"] for item in result["table_infos"][0]["columns"]] == [
            "amount",
            "id",
        ]
        assert result["metric_infos"][0]["name"] == "GMV"
        assert [event["status"] for event in events] == ["running", "success"]
        result = await merge_retrieved_info(
            {
                "retrieved_columns": [amount, key],
                "retrieved_values": [],
                "retrieved_metrics": [],
            },
            rt,
        )
        assert len(result["table_infos"][0]["columns"]) == 2

    async def test_merge_empty_and_repository_failure(self, mocker):
        repo = mocker.Mock(
            get_table_info_by_id=mocker.AsyncMock(
                side_effect=RuntimeError("meta offline")
            ),
            get_key_columns_by_table_id=mocker.AsyncMock(return_value=[]),
        )
        rt, events = runtime(meta_mysql_repository=repo)
        assert await merge_retrieved_info(
            {"retrieved_columns": [], "retrieved_values": [], "retrieved_metrics": []},
            rt,
        ) == {"table_infos": [], "metric_infos": []}
        with pytest.raises(RuntimeError, match="meta offline"):
            await merge_retrieved_info(
                {
                    "retrieved_columns": [column()],
                    "retrieved_values": [],
                    "retrieved_metrics": [],
                },
                rt,
            )
        assert events[-1]["status"] == "error"

    async def test_sql_validation_and_execution_emit_expected_outcomes(self, mocker):
        dw = mocker.Mock(
            validate_sql=mocker.AsyncMock(),
            execute_sql=mocker.AsyncMock(return_value=[{"总额": 10}]),
        )
        rt, events = runtime(dw_mysql_repository=dw)
        assert await validate_sql({"sql": "select 1"}, rt) == {"error": None}
        dw.validate_sql.side_effect = SQLAlchemyError("missing column")
        result = await validate_sql({"sql": "select missing"}, rt)
        assert "missing column" in result["error"]
        dw.validate_sql.side_effect = RuntimeError("transport error")
        with pytest.raises(RuntimeError):
            await validate_sql({"sql": "select 1"}, rt)
        await execute_sql({"sql": "select 1"}, rt)
        assert events[-1] == {"type": "result", "data": [{"总额": 10}]}
        dw.execute_sql.side_effect = RuntimeError("DW offline")
        with pytest.raises(RuntimeError):
            await execute_sql({"sql": "select 1"}, rt)
        assert events[-1]["status"] == "error"

    async def test_keyword_extraction_includes_original_and_deduplicates(self, mocker):
        rt, _ = runtime()
        mocker.patch(
            "app.agent.nodes.extract_keywords.jieba.analyse.extract_tags",
            return_value=["销售额", "销售额"],
        )
        result = await extract_keywords({"query": "销售额"}, rt)
        assert result["keywords"] == ["销售额"]

    async def test_llm_recall_nodes_use_real_prompts_and_parsers_and_deduplicate(
        self, mocker
    ):
        cases = [
            (
                "recall_column",
                "column_qdrant_repository",
                "retrieved_columns",
                column(),
            ),
            (
                "recall_metric",
                "metric_qdrant_repository",
                "retrieved_metrics",
                metric(),
            ),
            (
                "recall_value",
                "value_es_repository",
                "retrieved_values",
                ValueInfo("v1", "华东", "regions.name"),
            ),
        ]
        for name, dependency, result_key, entity in cases:
            module = import_module(f"app.agent.nodes.{name}")
            prompts = []

            def model(prompt, prompts=prompts):
                prompts.append(prompt.to_string())
                return '["华东", "销售额", "销售额"]'

            repo = mocker.Mock(search=mocker.AsyncMock(return_value=[entity, entity]))
            embeddings = mocker.Mock(aembed_query=mocker.AsyncMock(return_value=[1.0]))
            rt, events = runtime(**{dependency: repo, "embedding_client": embeddings})
            mocker.patch.object(module, "get_llm", return_value=RunnableLambda(model))
            result = await getattr(module, name)(state(), rt)
            assert result[result_key] == [entity]
            assert repo.search.await_count == 2
            assert "华东销售额" in prompts[0]
            assert events[-1]["status"] == "success"
            repo.search.side_effect = RuntimeError("search failed")
            mocker.patch.object(module, "get_llm", return_value=RunnableLambda(model))
            with pytest.raises(RuntimeError):
                await getattr(module, name)(state(), rt)
            assert events[-1]["status"] == "error"

    async def test_filter_and_sql_nodes_respect_prompt_context(self, mocker):
        cases = [
            ("filter_table", '{"orders":["amount"]}', "table_infos"),
            ("filter_metric", '["GMV"]', "metric_infos"),
            ("generate_sql", "select sum(amount) from orders", "sql"),
            ("correct_sql", "select amount from orders", "sql"),
        ]
        for name, response, key in cases:
            module = import_module(f"app.agent.nodes.{name}")
            prompts = []

            def model(prompt, prompts=prompts, response=response):
                prompts.append(prompt.to_string())
                return response

            rt, events = runtime()
            mocker.patch.object(module, "get_llm", return_value=RunnableLambda(model))
            result = await getattr(module, name)(deepcopy(state()), rt)
            assert "华东销售额" in prompts[0]
            if name == "filter_table":
                assert result[key][0]["columns"] == [{"name": "amount"}]
            elif name == "filter_metric":
                assert result[key] == [{"name": "GMV"}]
            else:
                assert result[key] == response
                assert "2026-09-28" in prompts[0]
                if name == "correct_sql":
                    assert "unknown column" in prompts[0]
            assert events[-1]["status"] == "success"

            def fail(prompt):
                raise RuntimeError("LLM unavailable")

            mocker.patch.object(module, "get_llm", return_value=RunnableLambda(fail))
            with pytest.raises(RuntimeError):
                await getattr(module, name)(deepcopy(state()), rt)
            assert events[-1]["status"] == "error"

    async def test_filters_handle_empty_selections_and_invalid_model_json(self, mocker):
        for name, response, key in [
            ("filter_table", "{}", "table_infos"),
            ("filter_metric", "[]", "metric_infos"),
        ]:
            module = import_module(f"app.agent.nodes.{name}")
            rt, events = runtime()
            mocker.patch.object(
                module,
                "get_llm",
                return_value=RunnableLambda(lambda _, response=response: response),
            )
            assert (await getattr(module, name)(deepcopy(state()), rt))[key] == []
            mocker.patch.object(
                module, "get_llm", return_value=RunnableLambda(lambda _: "not JSON")
            )
            with pytest.raises(OutputParserException):
                await getattr(module, name)(deepcopy(state()), rt)
            assert events[-1]["status"] == "error"

    async def test_extra_context_uses_fixed_date_quarter_and_reports_failure(
        self, mocker
    ):
        from datetime import datetime

        module = import_module("app.agent.nodes.add_extra_context")
        dw = mocker.Mock(
            get_db_info=mocker.AsyncMock(
                return_value={"dialect": "mysql", "version": "8.4"}
            )
        )
        rt, events = runtime(dw_mysql_repository=dw)
        clock = mocker.patch.object(module, "datetime")
        clock.now.return_value = datetime(2026, 12, 31, tzinfo=UTC)
        result = await module.add_extra_context({}, rt)
        assert result["date_info"]["quarter"] == "Q4"
        assert result["db_info"]["version"] == "8.4"
        dw.get_db_info.side_effect = RuntimeError("offline")
        with pytest.raises(RuntimeError):
            await module.add_extra_context({}, rt)
        assert events[-1]["status"] == "error"

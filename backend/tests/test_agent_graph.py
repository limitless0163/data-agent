import pytest

from app.agent.graph import build_graph


class TestAgentGraph:
    def test_compiled_graph_contains_all_agent_nodes(self):
        graph = build_graph()
        node_names = set(graph.get_graph().nodes)
        assert {
            "extract_keywords",
            "recall_column",
            "recall_value",
            "recall_metric",
            "merge_retrieved_info",
            "filter_metric",
            "filter_table",
            "add_extra_context",
            "generate_sql",
            "validate_sql",
            "correct_sql",
            "execute_sql",
        }.issubset(node_names)


class TestAgentGraphFlow:
    @pytest.mark.parametrize("correction", [False, True])
    async def test_real_graph_success_and_sql_correction_paths(
        self, mocker, correction
    ):
        import json

        from agent_fixture import (
            SQL,
            collaborators,
            deterministic_model,
        )
        from sqlalchemy.exc import SQLAlchemyError

        from app.services.query_service import QueryService

        context = collaborators(mocker)
        dw = context["dw_mysql_repository"]
        if correction:
            dw.validate_sql.side_effect = SQLAlchemyError("unknown column")
        with deterministic_model():
            service = QueryService(**context)
            events = [
                json.loads(frame[6:])
                async for frame in service.query(
                    "测试校正" if correction else "华东销售额"
                )
            ]
        assert events[-1] == {
            "type": "result",
            "data": [{"地区": "华东", "销售额": "30.50"}],
        }
        dw.execute_sql.assert_awaited_once_with(SQL)
        completed_steps = {
            event["step"]
            for event in events
            if event["type"] == "progress" and event["status"] == "success"
        }
        assert ("校正SQL" in completed_steps) == correction
        assert {
            "抽取关键字",
            "召回字段",
            "召回字段取值",
            "召回指标",
            "合并召回信息",
            "过滤指标",
            "过滤表格",
            "添加额外上下文信息",
            "生成SQL",
            "执行SQL",
        }.issubset(completed_steps)
        assert (
            sum(
                event.get("step") == "生成SQL" and event.get("status") == "running"
                for event in events
            )
            == 1
        )

    async def test_llm_failure_stops_before_sql_execution_and_is_an_sse_error(
        self, mocker
    ):
        import json

        from agent_fixture import collaborators, deterministic_model

        from app.services.query_service import QueryService

        context = collaborators(mocker)
        with deterministic_model():
            events = [
                json.loads(frame[6:])
                async for frame in QueryService(**context).query("模型故障")
            ]
        assert events[-1] == {"type": "error", "message": "测试模型不可用"}
        context["dw_mysql_repository"].execute_sql.assert_not_awaited()

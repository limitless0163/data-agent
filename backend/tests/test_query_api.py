import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.context import request_id_ctx_var
from app.services.query_service import QueryService


def parse_frames(frames):
    return [json.loads(frame.removeprefix("data: ").strip()) for frame in frames]


@pytest.fixture
def query_service():
    return QueryService(*[object() for _ in range(6)])


async def collect(service, query):
    return [frame async for frame in service.query(query)]


async def test_serializes_custom_events_and_decimal_with_fresh_request_state(
    query_service, mocker
):
    calls = []

    async def stream(**kwargs):
        calls.append(kwargs)
        yield {"type": "progress", "step": "执行SQL", "status": "running"}
        yield {"type": "result", "data": [{"金额": Decimal("12.30")}]}

    mocker.patch("app.services.query_service.graph", SimpleNamespace(astream=stream))
    results = await asyncio.gather(
        *[collect(query_service, query) for query in ["第一问", "第二问"]]
    )
    assert parse_frames(results[0])[-1]["data"] == [{"金额": "12.30"}]
    assert all(frame.endswith("\n\n") for frame in results[0])
    assert "执行SQL" in results[0][0]
    assert calls[0]["input"] is not calls[1]["input"]
    assert calls[0]["context"] is not calls[1]["context"]
    assert [call["input"]["query"] for call in calls] == ["第一问", "第二问"]
    assert calls[0]["stream_mode"] == "custom"
    assert (
        calls[0]["context"]["dw_mysql_repository"] is query_service.dw_mysql_repository
    )


async def test_partial_progress_survives_graph_failure(query_service, mocker):
    async def stream(**kwargs):
        yield {"type": "progress", "step": "生成SQL", "status": "running"}
        raise RuntimeError("模型不可用")

    mocker.patch("app.services.query_service.graph", SimpleNamespace(astream=stream))
    events = parse_frames(await collect(query_service, "问题"))
    assert events[-1] == {"type": "error", "message": "模型不可用"}
    assert len(events) == 2


async def test_cancellation_is_not_converted_into_business_error(query_service, mocker):
    async def stream(**kwargs):
        raise asyncio.CancelledError()
        yield

    mocker.patch("app.services.query_service.graph", SimpleNamespace(astream=stream))
    with pytest.raises(asyncio.CancelledError):
        await collect(query_service, "问题")


def test_valid_query_streams_using_dependency_override(api_client, api_state):
    with api_client.stream("POST", "/api/query", json={"query": "销售额"}) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        response.read()
        assert parse_frames([response.text]) == [{"type": "result", "data": []}]
    assert api_state.seen == ["销售额"]


@pytest.mark.parametrize(
    "payload", [{}, {"query": None}, {"query": 123}, {"query": []}, {"query": {}}]
)
def test_invalid_payloads_are_rejected_before_service_execution(
    api_client, api_state, payload
):
    response = api_client.post("/api/query", json=payload)
    assert response.status_code == 422
    assert api_state.seen == []


def test_invalid_json_is_rejected_before_service_execution(api_client, api_state):
    response = api_client.post(
        "/api/query", content="{bad", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert api_state.seen == []


def test_current_string_contract_accepts_empty_query(api_client, api_state):
    # Preserve the API's existing string-only contract without a new length policy.
    response = api_client.post("/api/query", json={"query": ""})
    assert response.status_code == 200
    assert api_state.seen == [""]


def test_http_method_and_openapi_contract(api_client):
    assert api_client.get("/api/query").status_code == 405
    spec = api_client.get("/openapi.json").json()
    assert "post" in spec["paths"]["/api/query"]
    assert spec["components"]["schemas"]["QuerySchema"]["required"] == ["query"]


def test_concurrent_requests_have_distinct_ids_and_restore_context(
    api_client, api_state
):
    before = request_id_ctx_var.get()
    with ThreadPoolExecutor(max_workers=3) as workers:
        responses = list(
            workers.map(
                lambda i: api_client.post("/api/query", json={"query": str(i)}),
                range(3),
            )
        )
    assert all(response.status_code == 200 for response in responses)
    assert len(set(api_state.request_ids)) == 3
    assert request_id_ctx_var.get() == before

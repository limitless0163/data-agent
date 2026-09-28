"""Pytest isolation is installed before test collection imports the application."""

import socket
from types import SimpleNamespace

import pytest
from bootstrap import configure
from fastapi.testclient import TestClient

_runtime = configure()
_runtime.__enter__()


def pytest_unconfigure(config):
    _runtime.__exit__(None, None, None)


@pytest.fixture(autouse=True)
def isolated_test(monkeypatch):
    def deny_network(*args, **kwargs):
        raise AssertionError("Tests must mock external network connections")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket.socket, "connect_ex", deny_network)
    from app.agent.llm import get_llm
    from app.core.context import request_id_ctx_var

    get_llm.cache_clear()
    token = request_id_ctx_var.set("test-request")
    try:
        yield
    finally:
        get_llm.cache_clear()
        request_id_ctx_var.reset(token)


@pytest.fixture
async def qdrant_client():
    # Async resources must close on the same per-test event loop.
    from qdrant_client import AsyncQdrantClient

    client = AsyncQdrantClient(":memory:")
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
def api_state():
    return SimpleNamespace(seen=[], request_ids=[])


@pytest.fixture
def api_client(api_state, mocker, monkeypatch):
    import app.core.lifespan as lifecycle
    from app.core.context import request_id_ctx_var
    from app.dependencies.query import get_query_service
    from app.main import app

    class FakeService:
        async def query(self, query):
            api_state.seen.append(query)
            api_state.request_ids.append(str(request_id_ctx_var.get()))
            yield 'data: {"type":"result","data":[]}\n\n'

    # Run the production lifespan through TestClient while replacing external clients.
    managers = {}
    for name in (
        "embedding_client_manager",
        "qdrant_client_manager",
        "es_client_manager",
        "meta_mysql_client_manager",
        "dw_mysql_client_manager",
    ):
        manager = mocker.Mock(init=mocker.Mock(), close=mocker.AsyncMock())
        monkeypatch.setattr(lifecycle, name, manager)
        managers[name] = manager
    monkeypatch.setattr(
        app,
        "dependency_overrides",
        {**app.dependency_overrides, get_query_service: lambda: FakeService()},
    )
    with TestClient(app) as client:
        yield client
    for name, manager in managers.items():
        manager.init.assert_called_once()
        if name != "embedding_client_manager":
            manager.close.assert_awaited_once()

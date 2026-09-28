"""Test-only ASGI entrypoint. Never add test switches to the production application."""

import os
import socket
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from pytest import MonkeyPatch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "tests"))
for name in list(os.environ):
    if name.startswith("DATA_AGENT_") or name == "DEEPSEEK_API_KEY":
        del os.environ[name]
from bootstrap import configure

_runtime = configure()
_runtime.__enter__()

from agent_fixture import collaborators, deterministic_model
from app.dependencies.query import get_query_service
from app.main import app
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.services.query_service import QueryService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

original_connect = socket.socket.connect
original_connect_ex = socket.socket.connect_ex


def loopback_only(original):
    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6) and address[0] not in (
            "127.0.0.1",
            "::1",
        ):
            raise AssertionError("E2E must not contact external services")
        return original(sock, address)

    return connect


@asynccontextmanager
async def test_lifespan(_app):
    with deterministic_model(), MonkeyPatch.context() as patches:
        patches.setattr(socket.socket, "connect", loopback_only(original_connect))
        patches.setattr(socket.socket, "connect_ex", loopback_only(original_connect_ex))
        try:
            yield
        finally:
            _runtime.__exit__(None, None, None)


class TestDWRepository(DWMySQLRepository):
    async def get_db_info(self):
        # Prompts target MySQL; SQL exercised here uses the common SQL subset.
        return {"dialect": "mysql", "version": "8.4"}


async def test_query_service():
    # Each request owns a new, disposable DB; no global fixture state or live DB URLs.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "create table orders (id integer primary key, region text, amount numeric)"
                )
            )
            await connection.execute(
                text(
                    "insert into orders values (1, '华东', 10.25), (2, '华东', 20.25), (3, '华南', 99)"
                )
            )
        async with async_sessionmaker(engine)() as session:
            context = collaborators()
            context["dw_mysql_repository"] = TestDWRepository(session)
            yield QueryService(**context)
    finally:
        await engine.dispose()


app.router.lifespan_context = test_lifespan
app.dependency_overrides[get_query_service] = test_query_service

from types import SimpleNamespace

import pytest

from app.core.lifespan import lifespan
from app.dependencies import query as dependencies


class TestDependency:
    @pytest.mark.parametrize(
        "provider,manager_name",
        [
            (dependencies.get_meta_session, "meta_mysql_client_manager"),
            (dependencies.get_dw_session, "dw_mysql_client_manager"),
        ],
    )
    @pytest.mark.parametrize("fail", [False, True])
    async def test_session_providers_close_on_success_and_failure(
        self, mocker, provider, manager_name, fail
    ):
        session = object()
        cm = mocker.AsyncMock()
        cm.__aenter__.return_value = session
        manager = mocker.Mock(session_factory=mocker.Mock(return_value=cm))
        mocker.patch.object(dependencies, manager_name, manager)
        generator = provider()
        assert await anext(generator) is session
        if fail:
            with pytest.raises(RuntimeError):
                await generator.athrow(RuntimeError("request failed"))
        else:
            await generator.aclose()
        cm.__aexit__.assert_awaited_once()

    async def test_repository_and_service_providers_keep_injected_clients(self, mocker):
        client = object()
        mocker.patch.object(
            dependencies, "embedding_client_manager", SimpleNamespace(client=client)
        )
        mocker.patch.object(
            dependencies, "qdrant_client_manager", SimpleNamespace(client=client)
        )
        mocker.patch.object(
            dependencies, "es_client_manager", SimpleNamespace(client=client)
        )
        assert await dependencies.get_embedding_client() is client
        for provider in [
            dependencies.get_column_qdrant_repository,
            dependencies.get_metric_qdrant_repository,
            dependencies.get_value_es_repository,
        ]:
            assert (await provider()).client is client
        session = object()
        assert (
            await dependencies.get_meta_mysql_repository(session)
        ).session is session
        assert (await dependencies.get_dw_mysql_repository(session)).session is session
        deps = [object() for _ in range(6)]
        service = await dependencies.get_query_service(*deps)
        assert service.embedding_client is deps[0]
        assert service.dw_mysql_repository is deps[-1]


class TestLifespan:
    @pytest.mark.parametrize("failure", [None, "body", "startup", "close"])
    async def test_resources_close_even_when_app_body_or_startup_fails(
        self, mocker, failure
    ):
        managers = {
            name: mocker.Mock(init=mocker.Mock(), close=mocker.AsyncMock())
            for name in [
                "embedding_client_manager",
                "qdrant_client_manager",
                "es_client_manager",
                "meta_mysql_client_manager",
                "dw_mysql_client_manager",
            ]
        }
        if failure == "startup":
            managers["dw_mysql_client_manager"].init.side_effect = RuntimeError(
                "startup"
            )
        if failure == "close":
            managers["dw_mysql_client_manager"].close.side_effect = RuntimeError(
                "close"
            )
        mocker.patch.multiple("app.core.lifespan", **managers)

        async def run():
            async with lifespan(mocker.Mock()):
                if failure == "body":
                    raise RuntimeError("body")

        if failure:
            with pytest.raises(RuntimeError):
                await run()
        else:
            await run()
        for name in [
            "qdrant_client_manager",
            "es_client_manager",
            "meta_mysql_client_manager",
        ]:
            managers[name].close.assert_awaited_once()
        assert managers["dw_mysql_client_manager"].close.await_count == (
            0 if failure == "startup" else 1
        )

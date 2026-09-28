import pytest

from app.core.config.app_config import DBConfig, ESConfig, QdrantConfig
from app.db.es_client_manager import ESClientManager
from app.db.mysql_client_manager import MysqlClientManager
from app.db.qdrant_client_manager import QdrantClientManager


class TestMysqlClientManager:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.manager = MysqlClientManager(
            DBConfig(
                host="mysql.example",
                port=3307,
                user="agent",
                password="secret",
                database="meta",
            )
        )

    def test_get_url_includes_connection_settings(self):
        assert (
            self.manager._get_url()
            == "mysql+asyncmy://agent:secret@mysql.example:3307/meta?charset=utf8mb4"
        )

    def test_init_creates_engine_and_session_factory(self, mocker):
        create_engine = mocker.patch("app.db.mysql_client_manager.create_async_engine")
        sessionmaker = mocker.patch("app.db.mysql_client_manager.async_sessionmaker")
        engine = mocker.Mock()
        create_engine.return_value = engine
        self.manager.init()
        create_engine.assert_called_once_with(
            url=self.manager._get_url(), pool_size=10, pool_pre_ping=True
        )
        sessionmaker.assert_called_once_with(
            engine, autoflush=True, expire_on_commit=False, autobegin=True
        )
        assert self.manager.engine is engine


class TestAsyncMysqlClientManager:
    async def test_close_disposes_engine(self, mocker):
        manager = MysqlClientManager(
            DBConfig("mysql.example", 3306, "agent", "secret", "meta")
        )
        manager.engine = mocker.Mock()
        manager.engine.dispose = mocker.AsyncMock()
        await manager.close()
        manager.engine.dispose.assert_awaited_once_with()


class TestESClientManager:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.manager = ESClientManager(
            ESConfig(host="search.example", port=9201, index_name="values")
        )

    def test_init_creates_async_client(self, mocker):
        client_class = mocker.patch("app.db.es_client_manager.AsyncElasticsearch")
        self.manager.init()
        client_class.assert_called_once_with(hosts=["http://search.example:9201"])
        assert self.manager.client is client_class.return_value


class TestAsyncESClientManager:
    async def test_close_closes_client(self, mocker):
        manager = ESClientManager(
            ESConfig(host="search.example", port=9200, index_name="values")
        )
        manager.client = mocker.Mock()
        manager.client.close = mocker.AsyncMock()
        await manager.close()
        manager.client.close.assert_awaited_once_with()


class TestQdrantClientManager:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.manager = QdrantClientManager(
            QdrantConfig(host="vector.example", port=6334, embedding_size=1024)
        )

    def test_init_creates_async_client(self, mocker):
        client_class = mocker.patch("app.db.qdrant_client_manager.AsyncQdrantClient")
        self.manager.init()
        client_class.assert_called_once_with(url="http://vector.example:6334")
        assert self.manager.client is client_class.return_value


class TestAsyncQdrantClientManager:
    async def test_close_closes_client(self, mocker):
        manager = QdrantClientManager(
            QdrantConfig(host="vector.example", port=6333, embedding_size=1024)
        )
        manager.client = mocker.Mock()
        manager.client.close = mocker.AsyncMock()
        await manager.close()
        manager.client.close.assert_awaited_once_with()

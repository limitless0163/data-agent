from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, patch

from app.core.config.app_config import DBConfig, ESConfig, QdrantConfig
from app.db.es_client_manager import ESClientManager
from app.db.mysql_client_manager import MysqlClientManager
from app.db.qdrant_client_manager import QdrantClientManager


class MysqlClientManagerTests(TestCase):
    def setUp(self):
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
        self.assertEqual(
            self.manager._get_url(),
            "mysql+asyncmy://agent:secret@mysql.example:3307/meta?charset=utf8mb4",
        )

    @patch("app.db.mysql_client_manager.async_sessionmaker")
    @patch("app.db.mysql_client_manager.create_async_engine")
    def test_init_creates_engine_and_session_factory(self, create_engine, sessionmaker):
        engine = Mock()
        create_engine.return_value = engine

        self.manager.init()

        create_engine.assert_called_once_with(
            url=self.manager._get_url(),
            pool_size=10,
            pool_pre_ping=True,
        )
        sessionmaker.assert_called_once_with(
            engine,
            autoflush=True,
            expire_on_commit=False,
            autobegin=True,
        )
        self.assertIs(self.manager.engine, engine)


class AsyncMysqlClientManagerTests(IsolatedAsyncioTestCase):
    async def test_close_disposes_engine(self):
        manager = MysqlClientManager(
            DBConfig("mysql.example", 3306, "agent", "secret", "meta")
        )
        manager.engine = Mock()
        manager.engine.dispose = AsyncMock()

        await manager.close()

        manager.engine.dispose.assert_awaited_once_with()


class ESClientManagerTests(TestCase):
    def setUp(self):
        self.manager = ESClientManager(
            ESConfig(host="search.example", port=9201, index_name="values")
        )

    def test_init_creates_async_client(self):
        with patch("app.db.es_client_manager.AsyncElasticsearch") as client_class:
            self.manager.init()

        client_class.assert_called_once_with(hosts=["http://search.example:9201"])
        self.assertIs(self.manager.client, client_class.return_value)


class AsyncESClientManagerTests(IsolatedAsyncioTestCase):
    async def test_close_closes_client(self):
        manager = ESClientManager(
            ESConfig(host="search.example", port=9200, index_name="values")
        )
        manager.client = Mock()
        manager.client.close = AsyncMock()

        await manager.close()

        manager.client.close.assert_awaited_once_with()


class QdrantClientManagerTests(TestCase):
    def setUp(self):
        self.manager = QdrantClientManager(
            QdrantConfig(host="vector.example", port=6334, embedding_size=1024)
        )

    def test_init_creates_async_client(self):
        with patch("app.db.qdrant_client_manager.AsyncQdrantClient") as client_class:
            self.manager.init()

        client_class.assert_called_once_with(url="http://vector.example:6334")
        self.assertIs(self.manager.client, client_class.return_value)


class AsyncQdrantClientManagerTests(IsolatedAsyncioTestCase):
    async def test_close_closes_client(self):
        manager = QdrantClientManager(
            QdrantConfig(host="vector.example", port=6333, embedding_size=1024)
        )
        manager.client = Mock()
        manager.client.close = AsyncMock()

        await manager.close()

        manager.client.close.assert_awaited_once_with()

import os

import pytest

from app.core.clients.embedding_client_manager import EmbeddingClientManager
from app.core.config.app_config import EmbeddingConfig, _load_app_config


class TestConfiguration:
    def test_environment_overrides_typed_config_and_key_precedence(self, mocker):
        env = {
            "DATA_AGENT_DB_META_HOST": "test-meta",
            "DATA_AGENT_DB_DW_HOST": "test-dw",
            "DATA_AGENT_DB_META_PORT": "3307",
            "DATA_AGENT_DB_DW_PORT": "3308",
            "DATA_AGENT_DB_USER": "test-user",
            "DATA_AGENT_DB_PASSWORD": "test-password",
            "DATA_AGENT_QDRANT_HOST": "test-vectors",
            "DATA_AGENT_QDRANT_PORT": "6334",
            "DATA_AGENT_EMBEDDING_HOST": "test-embedding",
            "DATA_AGENT_EMBEDDING_PORT": "80",
            "DATA_AGENT_ES_HOST": "test-search",
            "DATA_AGENT_ES_PORT": "9201",
            "DATA_AGENT_LLM_API_KEY": "preferred-test-key",
            "DEEPSEEK_API_KEY": "fallback-test-key",
        }
        mocker.patch.dict(os.environ, env, clear=True)
        mocker.patch("app.core.config.app_config.load_dotenv")
        config = _load_app_config()
        assert (config.db_meta.host, config.db_meta.port) == ("test-meta", 3307)
        assert (config.db_dw.host, config.db_dw.port) == ("test-dw", 3308)
        assert config.db_meta.password == config.db_dw.password
        assert config.db_meta.user == "test-user"
        assert config.qdrant.port == 6334
        assert config.embedding.port == 80
        assert config.es.host == "test-search"
        assert config.llm.api_key == "preferred-test-key"
        mocker.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fallback"}, clear=True)
        mocker.patch("app.core.config.app_config.load_dotenv")
        assert _load_app_config().llm.api_key == "fallback"

    def test_invalid_environment_port_fails_early(self, mocker):
        mocker.patch.dict(
            os.environ, {"DATA_AGENT_DB_META_PORT": "invalid"}, clear=True
        )
        mocker.patch("app.core.config.app_config.load_dotenv")
        with pytest.raises(ValueError):
            _load_app_config()

    def test_embedding_client_uses_configured_endpoint(self, mocker):
        manager = EmbeddingClientManager(EmbeddingConfig("test-host", 80, "bge"))
        client = mocker.patch(
            "app.core.clients.embedding_client_manager.HuggingFaceEndpointEmbeddings"
        )
        manager.init()
        client.assert_called_once_with(model="http://test-host:80")
        assert manager.client is client.return_value

import pytest

from app.agent.llm import get_llm
from app.core.config.app_config import app_config


class TestLLMConfiguration:
    @pytest.fixture(autouse=True)
    def setup(self):
        get_llm.cache_clear()
        yield
        get_llm.cache_clear()

    def test_get_llm_uses_runtime_configuration(self, mocker):
        init_chat_model = mocker.patch("app.agent.llm.init_chat_model")
        llm = get_llm()
        init_chat_model.assert_called_once_with(
            model=app_config.llm.model_name,
            api_key=app_config.llm.api_key,
            base_url=app_config.llm.base_url,
            temperature=0,
            extra_body={"thinking": {"type": "disabled"}},
        )
        assert llm is init_chat_model.return_value

    def test_get_llm_caches_the_constructed_instance(self, mocker):
        init_chat_model = mocker.patch("app.agent.llm.init_chat_model")
        first = get_llm()
        second = get_llm()
        init_chat_model.assert_called_once()
        assert first is second

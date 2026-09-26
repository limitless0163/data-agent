import unittest
from unittest.mock import patch

from app.agent.llm import create_llm
from app.core.config.app_config import app_config


class LLMConfigurationTests(unittest.TestCase):
    @patch("app.agent.llm.init_chat_model")
    def test_create_llm_uses_runtime_configuration(self, init_chat_model):
        llm = create_llm()

        init_chat_model.assert_called_once_with(
            model=app_config.llm.model_name,
            api_key=app_config.llm.api_key,
            base_url=app_config.llm.base_url,
            temperature=0,
            extra_body={"thinking": {"type": "disabled"}},
        )
        self.assertIs(llm, init_chat_model.return_value)

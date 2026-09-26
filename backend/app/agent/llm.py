from langchain.chat_models import init_chat_model

from app.core.config.app_config import app_config


def create_llm():
    return init_chat_model(
        model=app_config.llm.model_name,
        api_key=app_config.llm.api_key,
        base_url=app_config.llm.base_url,
        temperature=0,
        extra_body={"thinking": {"type": "disabled"}},
    )


llm = create_llm()

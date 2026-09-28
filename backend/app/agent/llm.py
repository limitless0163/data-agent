from functools import lru_cache

from langchain.chat_models import init_chat_model

from app.core.config.app_config import app_config


@lru_cache(maxsize=1)
def get_llm():
    """首次调用时创建并缓存模型客户端，供各查询节点复用。"""
    return init_chat_model(
        model=app_config.llm.model_name,
        api_key=app_config.llm.api_key,
        base_url=app_config.llm.base_url,
        temperature=0,
        extra_body={"thinking": {"type": "disabled"}},
    )

from langchain_openai import ChatOpenAI

from app.conf.app_config import app_config


llm = ChatOpenAI(
    model=app_config.llm.model_name,
    api_key=app_config.llm.api_key,
    base_url=app_config.llm.base_url,
    temperature=0,
    extra_body={"thinking": {"type": "disabled"}},
)


if __name__ == '__main__':
    for chunk in llm.stream("What is the meaning of life?"):
        print(chunk.text)

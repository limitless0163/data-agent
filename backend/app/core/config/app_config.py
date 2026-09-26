import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from omegaconf import OmegaConf


# 日志配置
@dataclass
class File:
    enable: bool
    level: str
    path: str
    rotation: str
    retention: str


@dataclass
class Console:
    enable: bool
    level: str


@dataclass
class LoggingConfig:
    file: File
    console: Console


# 数据库配置
@dataclass
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass
class QdrantConfig:
    host: str
    port: int
    embedding_size: int


@dataclass
class EmbeddingConfig:
    host: str
    port: int
    model: str


@dataclass
class ESConfig:
    host: str
    port: int
    index_name: str


@dataclass
class LLMConfig:
    model_name: str
    api_key: str
    base_url: str


@dataclass
class AppConfig:
    logging: LoggingConfig
    db_meta: DBConfig
    db_dw: DBConfig
    qdrant: QdrantConfig
    embedding: EmbeddingConfig
    es: ESConfig
    llm: LLMConfig


def _load_app_config() -> AppConfig:
    project_root = Path(__file__).resolve().parents[4]
    load_dotenv(project_root / ".env", override=False)

    config_file = Path(__file__).with_name('app_config.yaml')
    context = OmegaConf.load(config_file)

    # 容器部署时通过环境变量配置 Compose 服务名和运行时密钥；本地开发仍可使用仓库中的 YAML 默认配置。
    env_overrides = {
        "db_meta.host": ("DATA_AGENT_DB_META_HOST", str),
        "db_meta.port": ("DATA_AGENT_DB_META_PORT", int),
        "db_dw.host": ("DATA_AGENT_DB_DW_HOST", str),
        "db_dw.port": ("DATA_AGENT_DB_DW_PORT", int),
        "db_meta.user": ("DATA_AGENT_DB_USER", str),
        "db_dw.user": ("DATA_AGENT_DB_USER", str),
        "db_meta.password": ("DATA_AGENT_DB_PASSWORD", str),
        "db_dw.password": ("DATA_AGENT_DB_PASSWORD", str),
        "qdrant.host": ("DATA_AGENT_QDRANT_HOST", str),
        "qdrant.port": ("DATA_AGENT_QDRANT_PORT", int),
        "embedding.host": ("DATA_AGENT_EMBEDDING_HOST", str),
        "embedding.port": ("DATA_AGENT_EMBEDDING_PORT", int),
        "es.host": ("DATA_AGENT_ES_HOST", str),
        "es.port": ("DATA_AGENT_ES_PORT", int),
    }

    for path, (env_name, convert) in env_overrides.items():
        value = os.getenv(env_name)
        if value is not None:
            OmegaConf.update(context, path, convert(value))

    api_key = os.getenv("DATA_AGENT_LLM_API_KEY")
    if api_key is None:
        api_key = os.getenv("DEEPSEEK_API_KEY")
    if api_key is not None:
        OmegaConf.update(context, "llm.api_key", api_key)

    schema = OmegaConf.structured(AppConfig)
    return OmegaConf.to_object(OmegaConf.merge(schema, context))


app_config: AppConfig = _load_app_config()

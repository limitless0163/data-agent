from dataclasses import dataclass
import os
from pathlib import Path

from omegaconf import OmegaConf

from app.conf.config_loader import load_config


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


config_file = Path(__file__).parents[2] / 'conf' / 'app_config.yaml'
context = OmegaConf.load(config_file)
schema = OmegaConf.structured(AppConfig)
app_config: AppConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))

# Allow container deployments to use Compose DNS names and runtime secrets while
# keeping the checked-in YAML usable for local development.
app_config.db_meta.host = os.getenv("DATA_AGENT_DB_META_HOST", app_config.db_meta.host)
app_config.db_meta.port = int(os.getenv("DATA_AGENT_DB_META_PORT", app_config.db_meta.port))
app_config.db_dw.host = os.getenv("DATA_AGENT_DB_DW_HOST", app_config.db_dw.host)
app_config.db_dw.port = int(os.getenv("DATA_AGENT_DB_DW_PORT", app_config.db_dw.port))
app_config.db_meta.user = os.getenv("DATA_AGENT_DB_USER", app_config.db_meta.user)
app_config.db_dw.user = os.getenv("DATA_AGENT_DB_USER", app_config.db_dw.user)
app_config.db_meta.password = os.getenv("DATA_AGENT_DB_PASSWORD", app_config.db_meta.password)
app_config.db_dw.password = os.getenv("DATA_AGENT_DB_PASSWORD", app_config.db_dw.password)
app_config.qdrant.host = os.getenv("DATA_AGENT_QDRANT_HOST", app_config.qdrant.host)
app_config.qdrant.port = int(os.getenv("DATA_AGENT_QDRANT_PORT", app_config.qdrant.port))
app_config.embedding.host = os.getenv("DATA_AGENT_EMBEDDING_HOST", app_config.embedding.host)
app_config.embedding.port = int(os.getenv("DATA_AGENT_EMBEDDING_PORT", app_config.embedding.port))
app_config.es.host = os.getenv("DATA_AGENT_ES_HOST", app_config.es.host)
app_config.es.port = int(os.getenv("DATA_AGENT_ES_PORT", app_config.es.port))
app_config.llm.api_key = os.getenv("DATA_AGENT_LLM_API_KEY", app_config.llm.api_key)

if __name__ == '__main__':
    print(app_config.es.host)

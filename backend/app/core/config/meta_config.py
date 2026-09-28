from dataclasses import dataclass


@dataclass
class ColumnConfig:
    name: str
    role: str
    description: str
    alias: list[str]
    sync: bool  # 是否将该列的实际取值同步到全文索引


@dataclass
class TableConfig:
    name: str
    role: str
    description: str
    columns: list[ColumnConfig]


@dataclass
class MetricConfig:
    name: str
    description: str
    relevant_columns: list[str]  # 依赖字段的完整 ID，格式为“表名.字段名”
    alias: list[str]


@dataclass
class MetaConfig:
    tables: list[TableConfig] | None = None
    metrics: list[MetricConfig] | None = None

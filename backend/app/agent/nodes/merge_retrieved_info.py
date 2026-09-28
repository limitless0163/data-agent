from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import (
    ColumnInfoState,
    DataAgentState,
    MetricInfoState,
    TableInfoState,
)
from app.core.log import logger
from app.entities.column_info import ColumnInfo
from app.entities.table_info import TableInfo


async def merge_retrieved_info(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    """按字段 ID 合并三路召回，补齐指标依赖、取值示例和表关联键。"""
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "合并召回信息", "status": "running"})

    retrieved_columns = state["retrieved_columns"]
    retrieved_values = state["retrieved_values"]
    retrieved_metrics = state["retrieved_metrics"]

    meta_mysql_repository = runtime.context["meta_mysql_repository"]

    retrieved_columns_map: dict[str, ColumnInfo] = {
        retrieved_column.id: retrieved_column for retrieved_column in retrieved_columns
    }

    table_infos: list[TableInfoState] = []

    try:
        # 指标依赖的字段可能未被语义检索命中，需从元数据库补齐。
        for retrieved_metric in retrieved_metrics:
            relevant_columns = retrieved_metric.relevant_columns
            for relevant_column in relevant_columns:
                if relevant_column not in retrieved_columns_map:
                    column_info = await meta_mysql_repository.get_column_info_by_id(
                        relevant_column
                    )
                    retrieved_columns_map[relevant_column] = column_info

        # 把命中的实际取值补入示例，为 SQL 过滤条件提供候选值。
        for retrieved_value in retrieved_values:
            column_id = retrieved_value.column_id
            column_value = retrieved_value.value

            if column_id not in retrieved_columns_map:
                column_info = await meta_mysql_repository.get_column_info_by_id(
                    column_id
                )
                retrieved_columns_map[column_id] = column_info
            if column_value not in retrieved_columns_map[column_id].examples:
                retrieved_columns_map[column_id].examples.append(column_value)

        table_to_columns_map: dict[str, list[ColumnInfo]] = {}
        for column in retrieved_columns_map.values():
            table_id = column.table_id
            if table_id not in table_to_columns_map:
                table_to_columns_map[table_id] = []
            table_to_columns_map[table_id].append(column)

        # 即使未被召回，也补齐主外键，为后续生成跨表关联提供依据。
        for table_id, columns in table_to_columns_map.items():
            key_columns: list[
                ColumnInfo
            ] = await meta_mysql_repository.get_key_columns_by_table_id(table_id)

            column_ids = [column.id for column in columns]

            for key_column in key_columns:
                if key_column.id not in column_ids:
                    columns.append(key_column)

        for table_id, columns in table_to_columns_map.items():
            table: TableInfo = await meta_mysql_repository.get_table_info_by_id(
                table_id
            )
            columns = [
                ColumnInfoState(
                    name=column.name,
                    type=column.type,
                    role=column.role,
                    examples=column.examples,
                    description=column.description,
                    alias=column.alias,
                )
                for column in columns
            ]

            table_info_state = TableInfoState(
                name=table.name,
                role=table.role,
                description=table.description,
                columns=columns,
            )
            table_infos.append(table_info_state)

        metric_infos: list[MetricInfoState] = [
            MetricInfoState(
                name=metric_info.name,
                description=metric_info.description,
                relevant_columns=metric_info.relevant_columns,
                alias=metric_info.alias,
            )
            for metric_info in retrieved_metrics
        ]

        writer({"type": "progress", "step": "合并召回信息", "status": "success"})
        logger.info(
            f"合并召回信息: 表信息-{[table_info['name'] for table_info in table_infos]}, 指标信息-{[metric_info['name'] for metric_info in metric_infos]}"
        )
        return {"table_infos": table_infos, "metric_infos": metric_infos}

    except Exception as e:
        writer({"type": "progress", "step": "合并召回信息", "status": "error"})
        logger.error(f"合并召回信息失败: {e!s}")
        raise

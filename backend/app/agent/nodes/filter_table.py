import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import get_llm
from app.agent.prompt_loader import load_prompt
from app.agent.state import DataAgentState
from app.core.log import logger


async def filter_table(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "过滤表格", "status": "running"})

    query = state["query"]
    table_infos = state["table_infos"]

    try:
        prompt = PromptTemplate(
            template=load_prompt("filter_table_info"),
            input_variables=["query", "table_infos"],
        )
        llm = get_llm()
        output_parser = JsonOutputParser()

        chain = prompt | llm | output_parser

        result = await chain.ainvoke(
            {
                "query": query,
                "table_infos": yaml.dump(
                    table_infos, allow_unicode=True, sort_keys=False
                ),
            }
        )

        # 表和字段均遍历副本，避免原地删除时跳过候选项。
        for table_info in table_infos[:]:
            if table_info["name"] not in result:
                table_infos.remove(table_info)
            else:
                selected_columns = result[table_info["name"]]
                for column_info in table_info["columns"][:]:
                    if column_info["name"] not in selected_columns:
                        table_info["columns"].remove(column_info)

        writer({"type": "progress", "step": "过滤表格", "status": "success"})
        logger.info(
            f"过滤后的表信息: {[table_info['name'] for table_info in table_infos]}"
        )
        return {"table_infos": table_infos}

    except Exception as e:
        writer({"type": "progress", "step": "过滤表格", "status": "error"})
        logger.error(f"过滤表失败:{e!s}")
        raise

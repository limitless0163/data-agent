from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class DWMySQLRepository:
    """访问数据仓库；表名和字段名须来自可信元数据配置。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_column_types(self, table_name: str) -> dict[str, str]:
        sql = f"show columns from {table_name}"
        result = await self.session.execute(text(sql))
        return {row.Field: row.Type for row in result.fetchall()}

    async def get_column_values(self, table_name: str, column_name: str, limit: int):
        """返回最多 limit 个不同取值；不保证顺序，取值可能包含空值。"""
        sql = f"select distinct {column_name} from {table_name} limit {limit}"
        result = await self.session.execute(text(sql))
        return result.scalars().fetchall()

    async def get_db_info(self):
        result = await self.session.execute(text("select version()"))
        version = result.scalar()

        dialect = self.session.get_bind().dialect.name

        return {"version": version, "dialect": dialect}

    async def validate_sql(self, sql):
        """用 EXPLAIN 检查 SQL 能否规划；失败时抛出异常，不负责只读限制。"""
        await self.session.execute(text(f"explain {sql}"))

    async def execute_sql(self, sql):
        """将全部结果行转为字典列表，保留 Decimal、日期等原生值。"""
        result = await self.session.execute(text(sql))
        return [dict(row) for row in result.mappings().fetchall()]

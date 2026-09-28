from typing import Annotated

from app.dependencies.query import get_query_service
from app.schemas.query_schema import QuerySchema
from app.services.query_service import QueryService
from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

query_router = APIRouter()


@query_router.post("/api/query")
async def query(
    query: QuerySchema,
    query_service: Annotated[QueryService, Depends(get_query_service)],
):
    return StreamingResponse(
        query_service.query(query.query), media_type="text/event-stream"
    )

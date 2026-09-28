import asyncio
import os
import subprocess
import sys
import time

import asyncmy
import httpx
from app.core.log import logger


async def mysql_ready() -> bool:
    connection = await asyncmy.connect(
        host=os.getenv("DATA_AGENT_DB_META_HOST", "mysql"),
        port=int(os.getenv("DATA_AGENT_DB_META_PORT", "3306")),
        user=os.getenv("DATA_AGENT_DB_USER", "atguigu"),
        password=os.getenv("DATA_AGENT_DB_PASSWORD", "Atguigu.123"),
        db="dw",
        connect_timeout=3,
    )
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT COUNT(*) FROM fact_order")
            return (await cursor.fetchone())[0] > 0
    finally:
        connection.close()


async def dependency_status(client: httpx.AsyncClient) -> dict[str, bool]:
    results = {
        "mysql": False,
        "elasticsearch": False,
        "qdrant": False,
        "embeddings": False,
    }
    try:
        results["mysql"] = await mysql_ready()
    except Exception as e:  # noqa: BLE001 -- Any connection failure means MySQL is not ready yet.
        logger.debug(f"MySQL dependency is not ready: {e!s}")

    endpoints = {
        "elasticsearch": "http://elasticsearch:9200/",
        "qdrant": "http://qdrant:6333/healthz",
        "embeddings": "http://embeddings:80/health",
    }
    for name, url in endpoints.items():
        try:
            response = await client.get(url)
            results[name] = response.is_success
        except httpx.HTTPError as e:
            logger.debug(f"{name} dependency is not ready: {e!s}")
    return results


async def wait_until_ready() -> None:
    deadline = time.monotonic() + 900
    async with httpx.AsyncClient(timeout=4) as client:
        while time.monotonic() < deadline:
            status = await dependency_status(client)
            waiting = [name for name, ready in status.items() if not ready]
            if not waiting:
                print(
                    "MySQL, Elasticsearch, Qdrant, and the embedding model are ready.",
                    flush=True,
                )
                return
            print(f"Waiting for services: {', '.join(waiting)}", flush=True)
            await asyncio.sleep(5)
    raise TimeoutError(
        "Timed out waiting for database, search, vector, or embedding services"
    )


if __name__ == "__main__":
    asyncio.run(wait_until_ready())
    subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.build_meta_knowledge",
            "--conf",
            "app/core/config/meta_config.yaml",
        ],
        check=True,
    )

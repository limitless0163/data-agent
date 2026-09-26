import asyncio
import unittest

from app.core.context import request_id_ctx_var
from app.core.log import inject_request_id


class RequestIdLoggingTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_ids_remain_separate_across_concurrent_tasks(self):
        async def capture_request_id(request_id):
            token = request_id_ctx_var.set(request_id)
            try:
                record = {"extra": {}}
                inject_request_id(record)
                await asyncio.sleep(0)
                return record["extra"]["request_id"]
            finally:
                request_id_ctx_var.reset(token)

        request_ids = await asyncio.gather(
            capture_request_id("request-1"),
            capture_request_id("request-2"),
        )

        self.assertEqual(request_ids, ["request-1", "request-2"])

from pathlib import Path

import aiofiles
import aiofiles.os as os
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.job.slow_task import slow_task
from src.main import env, init_fastapi


@pytest_asyncio.fixture
async def client():  # noqa: F811
    app = FastAPI(root_path=env.ROOT_PATH)
    init_fastapi(app)
    await os.makedirs("data", exist_ok=True)
    LoggingDepends.init(path=Path("logs/test.log"))
    await SQLDepends.test()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    await SQLDepends.stop()


@pytest.mark.asyncio
async def test_post_upload(client: AsyncClient):
    filename = "assets/Rick Astley - Never Gonna Give You Up (Official Music Video).mkv"

    async with aiofiles.open(filename, "rb") as file:
        data = await file.read()
        res = await client.post(
            "/api/upload/test_upload.mkv",
            files={"file": data},
        )

    assert res.status_code == 200

    await slow_task()

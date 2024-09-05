import random
import urllib.parse
from pathlib import Path

import aiofiles
import pytest
import pytest_asyncio
from aiofiles import os
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import src.util.aioshutils as shutil
from main import env, init_fastapi
from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.job.slow_task import slow_task
from src.util.file import FileResolver


@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup():
    await shutil.rmtree(FileResolver.base_path, ignore_errors=True)
    await os.makedirs(FileResolver.base_path, exist_ok=True)
    await SQLDepends.test(drop_all=True)
    yield
    await SQLDepends.stop()


@pytest_asyncio.fixture(scope="session")
async def client():
    FileResolver.set_temp()
    app = FastAPI(root_path=env.ROOT_PATH)
    init_fastapi(app)

    LoggingDepends.init(path=Path("logs/testing.log"))

    port = random.randint(8000, 9000)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    yield lambda path: urllib.parse.urljoin(f"http://localhost:{port}", path)


@pytest.mark.asyncio
async def test_post_upload(client: AsyncClient):
    filename = "assets/Rick Astley - Never Gonna Give You Up (Official Music Video).mp4"
    assets = Path(filename)

    async with aiofiles.open(assets, "rb") as file:
        data = await file.read()
        res = await client.post(
            f"/api/upload/test_upload{assets.suffix}",
            files={"file": data},
        )

    assert res.status_code == 200

    await slow_task()

    await client.request(
        "MOVE",
        f"/api/upload/test_upload{assets.suffix}",
        headers={"Destination": f"/api/upload/test_upload2{assets.suffix}"},
    )

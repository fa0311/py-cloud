import asyncio
import random
import sys
import urllib.parse
from os import environ
from pathlib import Path

import pytest
import pytest_asyncio
from aiofiles import os
from sqlalchemy import select
from webdav3.client import Client

import src.util.aioshutils as shutil
from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.models.file import FileORM
from src.util.file import FileResolver

FileResolver.set_temp()


async def db_check(filename: str) -> bool:
    path = FileResolver.base_path.joinpath(filename)
    file_state = select(FileORM).where(FileORM.filename == str(path))

    async with SQLDepends.state.begin() as conn:
        res = await conn.execute(file_state)
        return bool(res.rowcount)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup():
    await shutil.rmtree(FileResolver.base_path, ignore_errors=True)
    await os.makedirs(FileResolver.base_path, exist_ok=True)
    await SQLDepends.test(drop_all=True)
    yield
    await SQLDepends.stop()


@pytest_asyncio.fixture(scope="session")
async def client():
    await LoggingDepends.init(path=Path("logs/test.log"))
    port = random.randint(8000, 9000)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "main.py",
        env={**environ, "TESTING": "true", "PORT": str(port)},
    )

    while True:
        try:
            await asyncio.open_connection("localhost", port)
            break
        except Exception:
            await asyncio.sleep(0.1)

    yield lambda path: urllib.parse.urljoin(f"http://localhost:{port}", path)
    process.terminate()


@pytest.mark.asyncio
async def test_webdav_list(client):
    options = {
        "webdav_hostname": client("/api/webdav"),
    }
    webdav = Client(options)
    res = webdav.list("/", get_info=True)
    assert res


@pytest.mark.asyncio
async def test_webdav_check(client):
    options = {
        "webdav_hostname": client("/api/webdav"),
    }
    webdav = Client(options)
    res = webdav.check("/")
    assert res is True


@pytest.mark.asyncio
async def test_webdav_upload(client):
    options = {
        "webdav_hostname": client("/api/webdav"),
    }
    filename = "assets/Rick Astley - Never Gonna Give You Up (Official Music Video).mkv"
    assets = Path(filename)
    webdav = Client(options)
    webdav.upload(assets.name, assets.as_posix())

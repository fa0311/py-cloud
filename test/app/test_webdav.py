import asyncio
import io
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
    LoggingDepends.init(path=Path("logs/test.log"))
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
    filename = "assets/Rick Astley - Never Gonna Give You Up (Official Music Video).mp4"
    assets = Path(filename)
    webdav = Client(options)
    webdav.upload(assets.name, assets.as_posix())


@pytest.mark.asyncio
async def test_webdav_e2ee(client):
    options = {
        "webdav_hostname": client("/api/webdav"),
    }

    webdav = Client(options)
    webdav.upload_to(io.BytesIO(b"hello world"), "/test.txt")
    b"".join(webdav.download_iter("/test.txt"))
    assert await db_check("test.txt")

    webdav.clean("/test.txt")
    assert not await db_check("test.txt")

    webdav.mkdir("/test")
    webdav.mkdir("/test/test")
    webdav.upload_to(io.BytesIO(b"hello world"), "/test/test/test.txt")
    b"".join(webdav.download_iter("/test/test/test.txt"))
    assert await db_check("test/test/test.txt")

    webdav.mkdir("/test/test2")
    webdav.move("/test/test/test.txt", "/test/test2/test.txt")
    b"".join(webdav.download_iter("/test/test2/test.txt"))
    assert await db_check("test/test2/test.txt")
    assert not await db_check("test/test/test.txt")

    webdav.copy("/test/test2/test.txt", "/test/test/test.txt")
    b"".join(webdav.download_iter("/test/test/test.txt"))
    assert await db_check("test/test/test.txt")
    assert await db_check("test/test2/test.txt")

    webdav.mkdir("/test/test3")
    try:
        webdav.move("test/test/test.txt", "/test/test3")
        assert False
    except Exception:
        assert await db_check("test/test/test.txt")
        assert not await db_check("test/test3/test.txt")

    webdav.clean("/test")
    assert not await db_check("test/test/test.txt")
    assert not await db_check("test/test2/test.txt")

    try:
        webdav.upload_to(io.BytesIO(b"hello world"), "/test/test/test.txt")
        assert False
    except Exception:
        assert not await db_check("test/test/test.txt")

    try:
        webdav.mkdir("/test/test")
        assert False
    except Exception:
        assert not await db_check("test/test")

    try:
        webdav.clean("/test")
        assert False
    except Exception:
        assert not await db_check("test")

    list = webdav.list("/.trashbin", get_info=True)

    webdav.clean(f"/.trashbin/{Path(list[1]['path']).name}/test")

    path = Path(list[1]["path"]).name
    webdav.copy(f"/.trashbin/{path}/test.txt", "/test.txt")
    assert await db_check("test.txt")

    webdav.move(f"/.trashbin/{path}/test.txt", "/test2.txt")
    assert await db_check("test2.txt")

    webdav.move("/test2.txt", "/.trashbin/test2.txt")
    assert not await db_check("/.trashbin/test2.txt")
    assert not await db_check("test2.txt")

    webdav.move("/.trashbin", "/test")

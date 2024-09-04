import os
import random
import threading
import urllib.parse
from pathlib import Path

import pytest
import pytest_asyncio
import uvicorn
from fastapi import FastAPI
from webdav3.client import Client

from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.main import env, init_fastapi


@pytest_asyncio.fixture
async def client():
    app = FastAPI(root_path=env.ROOT_PATH)
    init_fastapi(app)
    os.makedirs("data", exist_ok=True)
    LoggingDepends.init(path=Path("logs/test.log"))
    await SQLDepends.test()
    port = random.randint(49152, 65535)

    def run():
        uvicorn.run(app, host="0.0.0.0", port=port)

    threading.Thread(target=run, daemon=True).start()

    yield lambda path: urllib.parse.urljoin(f"http://localhost:{port}", path)
    await SQLDepends.stop()


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
    webdav = Client(options)
    webdav.upload(
        "/aaa.mkv",
        "assets/Rick Astley - Never Gonna Give You Up (Official Music Video).mkv",
    )

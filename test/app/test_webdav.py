import os
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

    def run():
        uvicorn.run(app, host="0.0.0.0", port=8000)

    threading.Thread(target=run, daemon=True).start()

    yield lambda path: urllib.parse.urljoin("http://localhost:8000", path)
    await SQLDepends.stop()


@pytest.mark.asyncio
async def test_webdav_list(client):
    options = {
        "webdav_hostname": client("/api/webdav"),
        # "webdav_hostname": "https://xn--p8jr3f0f.xn--w8j2f.com/remote.php/dav/files/yuki",
    }
    webdav = Client(options)
    res = webdav.list("/", get_info=True)


@pytest.mark.asyncio
async def test_webdav_check(client):
    options = {
        "webdav_hostname": client("/api/webdav"),
        # "webdav_hostname": "https://xn--p8jr3f0f.xn--w8j2f.com/remote.php/dav/files/yuki",
    }
    webdav = Client(options)
    res = webdav.check("/")
    assert res is True


@pytest.mark.asyncio
async def test_webdav_upload(client):
    options = {
        "webdav_hostname": client("/api/webdav"),
        # "webdav_hostname": "https://xn--p8jr3f0f.xn--w8j2f.com/remote.php/dav/files/yuki",
    }
    webdav = Client(options)
    webdav.upload(
        "/aaa.mkv",
        "assets/Rick Astley - Never Gonna Give You Up (Official Music Video).mkv",
    )

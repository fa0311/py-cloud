import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from webdav3.client import Client

from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.job.slow_task import slow_task
from src.main import app


@pytest.fixture
def client():  # noqa: F811
    shutil.rmtree("data", ignore_errors=True)
    LoggingDepends.init(path=Path("logs/test.log"))
    SQLDepends.test()
    yield TestClient(app)
    SQLDepends.stop()


def test_post_upload(client: TestClient):
    filename = "assets/Rick Astley - Never Gonna Give You Up (Official Music Video).mp4"
    with open(filename, "rb") as file:
        res = client.post(
            "/api/upload/test_upload.mp4",
            files={"file": file},
        )

    assert res.status_code == 200

    slow_task()


def test_webdav_list():
    options = {
        "webdav_hostname": "http://localhost:8000/api/webdav",
        # "webdav_hostname": "https://xn--p8jr3f0f.xn--w8j2f.com/remote.php/dav/files/yuki",
    }
    webdav = Client(options)
    webdav.list("/", get_info=True)


def test_webdav_check():
    options = {
        "webdav_hostname": "http://localhost:8000/api/webdav",
        # "webdav_hostname": "https://xn--p8jr3f0f.xn--w8j2f.com/remote.php/dav/files/yuki",
    }
    webdav = Client(options)
    webdav.check("/")


def test_webdav_upload():
    options = {
        "webdav_hostname": "http://localhost:8000/api/webdav",
        # "webdav_hostname": "https://xn--p8jr3f0f.xn--w8j2f.com/remote.php/dav/files/yuki",
    }
    webdav = Client(options)
    webdav.upload(
        "/aaa.mp4",
        "assets/Rick Astley - Never Gonna Give You Up (Official Music Video).mp4",
    )

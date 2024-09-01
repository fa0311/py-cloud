from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.job.slow_task import slow_task
from src.main import app


@pytest.fixture
def client():  # noqa: F811
    LoggingDepends.init(path=Path("logs/test.log"))
    SQLDepends.test()
    yield TestClient(app)
    SQLDepends.stop()


def test_post_upload(client: TestClient):
    with open("Voice Genius - AI x ゆっくり解説 [g0Ookp-8yUI].mp4", "rb") as file:
        res = client.post(
            "/api/upload/test_upload.mp4",
            files={"file": file},
        )

    assert res.status_code == 200

    slow_task()

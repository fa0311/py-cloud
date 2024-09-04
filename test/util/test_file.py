from pathlib import Path

import pytest

from src.util.file import FileResolver


@pytest.mark.asyncio
async def test_file():
    assert FileResolver.get_base_url(
        Path("data/aaaa"),
        Path("aaaa"),
    ) == Path("data")
    assert FileResolver.get_base_url(
        Path("data/aaaa/bbbb"),
        Path("aaaa/bbbb"),
    ) == Path("data")
    assert FileResolver.get_base_url(
        Path("data/aaaa/bbbb/cccc"),
        Path("aaaa/bbbb/cccc"),
    ) == Path("data")
    assert FileResolver.get_base_url(
        Path("data/aaaa/bbbb/cccc"),
        Path("bbbb/cccc"),
    ) == Path("data/aaaa")

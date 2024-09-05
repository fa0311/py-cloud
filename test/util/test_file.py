from pathlib import Path

import pytest

from src.util.file import FileResolver


@pytest.mark.asyncio
async def test_file():
    a = Path("data/aaaa")
    b = Path("aaaa")

    assert FileResolver.get_base_url(a, b) == Path("data")

    a = Path("data/aaaa/bbbb")
    b = Path("aaaa/bbbb")

    assert FileResolver.get_base_url(a, b) == Path("data")

    a = Path("data/aaaa/bbbb/cccc")
    b = Path("aaaa/bbbb/cccc")

    assert FileResolver.get_base_url(a, b) == Path("data")

    a = Path("data/aaaa/bbbb/cccc")
    b = Path("bbbb/cccc")

    assert FileResolver.get_base_url(a, b) == Path("data/aaaa")

import pathlib

import aiofiles.os as os
import pytest

from src.util.ffmpeg import FFmpegVideo, FFmpegWrapper


@pytest.mark.asyncio
async def test_ffprobe():
    path = "assets/Rick Astley - Never Gonna Give You Up (Official Music Video).mkv"
    res = await FFmpegWrapper.from_file(pathlib.Path(path))
    assert res.is_video()


@pytest.mark.asyncio
async def test_ffmpeg():
    pathname = "assets/Rick Astley - Never Gonna Give You Up (Official Music Video).mkv"
    path = pathlib.Path(pathname)
    temp_dir = pathlib.Path("data/test")
    await os.makedirs(temp_dir, exist_ok=True)
    res = await FFmpegVideo.from_file(path)
    await res.thumbnail(temp_dir, "test")
    await res.down_scale(temp_dir, "test", 360, 480)

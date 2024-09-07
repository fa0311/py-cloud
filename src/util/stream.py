import asyncio
from pathlib import Path
from typing import Optional

from aiofiles import open
from fastapi.responses import FileResponse


class Stream:
    @staticmethod
    async def read_file(file: Path, start: int, end: Optional[int]):
        try:
            async with open(file, "rb") as f:
                async for chunk in Stream.read(f, start, end):
                    yield chunk
        except asyncio.CancelledError:
            pass

    @staticmethod
    async def read(file, start: int, end: Optional[int]):
        try:
            await file.seek(start)
            chunk_size = FileResponse.chunk_size
            if end is None:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            else:
                while True:
                    size = min(chunk_size, end - start + 1)
                    if size == 0:
                        break
                    chunk = await file.read(size)
                    yield chunk
                    start += size

        except asyncio.CancelledError:
            pass

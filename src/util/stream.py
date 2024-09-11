import asyncio
from pathlib import Path

from aiofiles import open
from fastapi.responses import FileResponse


class Stream:
    @staticmethod
    async def read_file(file: Path, start: int, end: int):
        try:
            async with open(file, "rb") as f:
                async for chunk in Stream.read(f, start, end):
                    yield chunk
        except asyncio.CancelledError:
            pass

    @staticmethod
    async def read(file, start: int, end: int):
        try:
            await file.seek(start)
            for _ in range((end - start) // FileResponse.chunk_size):
                yield await file.read(FileResponse.chunk_size)
            yield await file.read((end - start) % FileResponse.chunk_size)

        except asyncio.CancelledError:
            pass

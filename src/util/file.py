import time
from functools import reduce
from pathlib import Path
from typing import Union
from urllib.parse import unquote, urlparse

import aiofiles.os as os


class FileResolver:
    base_path = Path("./data/data")
    temp_path = base_path.joinpath(".temp")
    trashbin_path = base_path.joinpath(".trashbin")

    @staticmethod
    def set_temp():
        FileResolver.base_path = Path("data/test")
        FileResolver.temp_path = FileResolver.base_path.joinpath(".temp")
        FileResolver.trashbin_path = FileResolver.base_path.joinpath(".trashbin")

    @staticmethod
    async def get_file(file_path: Union[str, Path]) -> Path:
        file = FileResolver.base_path.joinpath(file_path)
        await os.makedirs(file.parent, exist_ok=True)
        return file

    @staticmethod
    async def get_temp_from_data(file_path: Path) -> Path:
        relative_file = file_path.relative_to(FileResolver.base_path)
        temp = FileResolver.temp_path.joinpath(relative_file)
        await os.makedirs(temp.parent, exist_ok=True)
        return temp

    @staticmethod
    async def __get_trashbin(file_path: Union[str, Path]) -> Path:
        timestamp = time.strftime("%Y-%m-%d", time.localtime())
        trash_dir = FileResolver.trashbin_path.joinpath(timestamp)

        count = 0
        while await os.path.exists(trash_dir):
            trash_dir = FileResolver.trashbin_path.joinpath(f"{timestamp}-{count:04d}")
            count += 1

        trashbin = trash_dir.joinpath(file_path)
        await os.makedirs(trashbin.parent, exist_ok=True)
        return trashbin

    @staticmethod
    async def get_trashbin_from_data(file_path: Path) -> Path:
        relative_file = file_path.relative_to(FileResolver.base_path)
        return await FileResolver.__get_trashbin(relative_file)

    @staticmethod
    def get_base_url(pearent: Path, child: Path) -> Path:
        num = range(len(child.parts))
        base_url = reduce(lambda p, _: p.parent, num, pearent)
        return base_url

    @staticmethod
    async def from_url(baseurl: Path, url: str) -> Path:
        url_path = Path(unquote(urlparse(url).path))
        rename = await FileResolver.get_file(url_path.relative_to(baseurl))
        return rename

    @staticmethod
    async def get_content_type(path: Path):
        if await os.path.isdir(path):
            return "httpd/unix-directory"
        else:
            return "application/octet-stream"

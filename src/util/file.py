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
    async def get_file(file_path: Union[str, Path]) -> Path:
        file = FileResolver.base_path.joinpath(file_path)
        await os.makedirs(file.parent, exist_ok=True)
        return file

    @staticmethod
    async def get_temp_from_data(file_path: Path) -> Path:
        relative_file = file_path.relative_to(FileResolver.base_path)
        return await FileResolver.get_temp(relative_file)

    @staticmethod
    async def get_temp(file_path: Union[str, Path]) -> Path:
        temp = FileResolver.temp_path.joinpath(file_path)
        await os.makedirs(temp, exist_ok=True)
        return temp

    @staticmethod
    async def get_trashbin(file_path: Union[str, Path]) -> Path:
        timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime(time.time()))
        trashbin = FileResolver.trashbin_path.joinpath(timestamp).joinpath(file_path)
        await os.makedirs(trashbin.parent, exist_ok=True)
        return trashbin

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

import time
import uuid
from functools import reduce
from pathlib import Path
from typing import Awaitable, Callable, Union
from urllib.parse import unquote, urlparse


class FileResolver:
    base_path = Path("./data/data")
    metadata_path = base_path.joinpath(".metadata")
    trashbin_path = base_path.joinpath(".trashbin")

    @staticmethod
    def set_temp():
        FileResolver.base_path = Path("data/test")
        FileResolver.metadata_path = FileResolver.base_path.joinpath(".metadata")
        FileResolver.trashbin_path = FileResolver.base_path.joinpath(".trashbin")

    @staticmethod
    def get_file(file_path: Union[str, Path]) -> Path:
        file = FileResolver.base_path.joinpath(file_path)
        return file

    @staticmethod
    def get_metadata_from_uuid(uuid: uuid.UUID) -> Path:
        temp = FileResolver.metadata_path.joinpath(str(uuid))
        return temp

    @staticmethod
    async def __get_trashbin(
        file_path: Union[str, Path], exists: Callable[[Path], Awaitable[bool]]
    ) -> Path:
        timestamp = time.strftime("%Y-%m-%d", time.localtime())
        trash_dir = FileResolver.trashbin_path.joinpath(timestamp)

        count = 0
        while await exists(trash_dir):
            trash_dir = FileResolver.trashbin_path.joinpath(f"{timestamp}-{count:04d}")
            count += 1

        trashbin = trash_dir.joinpath(file_path)
        return trashbin

    @staticmethod
    async def get_trashbin_from_data(
        file_path: Path, exists: Callable[[Path], Awaitable[bool]]
    ) -> Path:
        relative_file = file_path.relative_to(FileResolver.base_path)
        return await FileResolver.__get_trashbin(relative_file, exists)

    @staticmethod
    def get_base_url(pearent: Path, child: Path) -> Path:
        num = range(len(child.parts))
        base_url = reduce(lambda p, _: p.parent, num, pearent)
        return base_url

    @staticmethod
    async def from_url(baseurl: Path, url: str) -> Path:
        url_path = Path(unquote(urlparse(url).path))
        rename = FileResolver.get_file(url_path.relative_to(baseurl))
        return rename

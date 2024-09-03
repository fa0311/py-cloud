import pathlib
from typing import Union

import aiofiles.os as os


class FileResolver:
    base_path = pathlib.Path("./data/data")
    temp_path = pathlib.Path("./data/temp")

    @staticmethod
    async def get_file(file_path: pathlib.Path) -> pathlib.Path:
        relative_file = file_path.relative_to(FileResolver.base_path)
        return await FileResolver.get_file_str(relative_file)

    @staticmethod
    async def get_file_str(file_path: Union[str, pathlib.Path]) -> pathlib.Path:
        file = FileResolver.base_path.joinpath(file_path)
        await os.makedirs(file.parent, exist_ok=True)
        return file

    @staticmethod
    async def get_temp(file_path: pathlib.Path) -> pathlib.Path:
        relative_file = file_path.relative_to(FileResolver.base_path)
        return await FileResolver.get_temp_str(relative_file)

    @staticmethod
    async def get_temp_str(file_path: Union[str, pathlib.Path]) -> pathlib.Path:
        temp = FileResolver.temp_path.joinpath(file_path)
        await os.makedirs(temp, exist_ok=True)
        return temp

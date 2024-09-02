import pathlib
from typing import Union


class FileResolver:
    base_path = pathlib.Path("./data/data")
    temp_path = pathlib.Path("./data/temp")

    @staticmethod
    def get_file(file_path: pathlib.Path) -> pathlib.Path:
        relative_file = file_path.relative_to(FileResolver.base_path)
        return FileResolver.get_file_str(relative_file)

    @staticmethod
    def get_file_str(file_path: Union[str, pathlib.Path]) -> pathlib.Path:
        file = FileResolver.base_path.joinpath(file_path)
        file.parent.mkdir(parents=True, exist_ok=True)
        return file

    @staticmethod
    def get_temp(file_path: pathlib.Path) -> pathlib.Path:
        relative_file = file_path.relative_to(FileResolver.base_path)
        return FileResolver.get_temp_str(relative_file)

    @staticmethod
    def get_temp_str(file_path: Union[str, pathlib.Path]) -> pathlib.Path:
        temp = FileResolver.temp_path.joinpath(file_path)
        temp.mkdir(parents=True, exist_ok=True)
        return temp

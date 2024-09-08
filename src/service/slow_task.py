from logging import Logger
from pathlib import Path
from typing import AsyncGenerator, Union

from aiofiles import open, os
from fastapi import Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from src.depends.sql import SQLDepends
from src.models.slow_task import SlowTaskModel, SlowTaskORM
from src.sql.file_crad import FileCRAD
from src.sql.file_lock_crad import FileLockCRADError, FileLockTransaction
from src.util import aioshutils as shutil
from src.util.file import FileResolver
from src.util.stream import Stream


class SuccessResponse(BaseModel):
    success: bool = True


class FileService:
    def __init__(
        self,
        request: Request,
        logger: Logger,
        session: AsyncSession,
    ):
        self.request = request
        self.logger = logger
        self.session = session

    def success_response(self) -> Union[Response, BaseModel]:
        return JSONResponse(content={}, status_code=200)

    def created_response(self) -> Union[Response, BaseModel]:
        return JSONResponse(content={}, status_code=201)

    def no_content_response(self) -> Union[Response, BaseModel]:
        return JSONResponse(content={}, status_code=204)

    def data_response(self, data) -> Union[Response, BaseModel]:
        return JSONResponse(content=data, status_code=200)

    def conflict_response(self) -> Union[Response, BaseModel]:
        return JSONResponse(content={}, status_code=409)

    def not_allowed_response(self) -> Union[Response, BaseModel]:
        return JSONResponse(content={}, status_code=405)

    def not_found_response(self) -> Union[Response, BaseModel]:
        return JSONResponse(content={}, status_code=404)

    def locked_response(self) -> Union[Response, BaseModel]:
        return JSONResponse(content={}, status_code=423)

    @staticmethod
    def error_decorator(func):
        async def wrapper(self: "FileService", *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            except FileLockCRADError as e:
                self.logger.error(e)
                return self.locked_response()
            except FileNotFoundError as e:
                self.logger.error(e)
                return self.not_found_response()
            except Exception as e:
                self.logger.error(e)
                return self.not_found_response()

        return wrapper

    async def get_base(self, href: Path, path: Path) -> list:
        raise NotImplementedError

    async def get_file(self, href: Path, path: Path) -> Union[dict, BaseModel]:
        raise NotImplementedError

    @error_decorator
    async def list(self, file_path: Path) -> Union[Response, BaseModel]:
        if FileResolver.base_path not in file_path.parents:
            return self.not_allowed_response()
        elif await os.path.isdir(file_path):
            responses = await self.get_base(Path(self.request.url.path), file_path)
            for file in await os.listdir(file_path.as_posix()):
                href = Path(self.request.url.path).joinpath(file)
                responses.append(await self.get_file(href, file_path.joinpath(file)))

            return self.data_response(responses)

        elif await os.path.isfile(file_path):
            href = Path(self.request.url.path)
            responses = [await self.get_file(href, file_path)]
            return self.data_response(responses)
        else:
            return self.not_found_response()

    @error_decorator
    async def upload(
        self, file_path: Path, stream: AsyncGenerator[bytes, None]
    ) -> Union[Response, BaseModel]:
        if FileResolver.base_path not in file_path.parents:
            return self.not_allowed_response()
        elif FileResolver.temp_path in file_path.parents:
            return self.not_allowed_response()
        elif FileResolver.trashbin_path in file_path.parents:
            return self.not_allowed_response()
        elif await os.path.exists(file_path):
            return self.conflict_response()
        else:
            async with FileLockTransaction(SQLDepends.state, file_path):
                async with open(file_path, "wb") as f:
                    async for chunk in stream:
                        await f.write(chunk)
                temp_dir = await FileResolver.get_temp_from_data(file_path)
                await os.makedirs(temp_dir, exist_ok=True)
                metadata = await FileCRAD(self.session).put(file_path)
                if metadata.video:
                    task_model = SlowTaskModel(
                        type="video_convert",
                        file_id=metadata.id,
                    )
                    self.session.add(SlowTaskORM.from_model(task_model))
            await self.session.commit()
            return self.created_response()

    @error_decorator
    async def download(
        self, file_path: Path
    ) -> Union[Response, BaseModel, StreamingResponse]:
        if FileResolver.base_path not in file_path.parents:
            return self.not_allowed_response()
        elif not await os.path.isfile(file_path):
            return self.not_found_response()
        elif self.request.headers.get("Range"):
            all = await os.path.getsize(file_path)
            start, end = self.request.headers["Range"].split("=")[1].split("-")
            start = int(start) if start else 0
            end = int(end) if end else all - 1
        else:
            all = await os.path.getsize(file_path)
            start = 0
            end = all - 1

        return StreamingResponse(
            Stream.read_file(file_path, start, end),
            headers={
                "Content-Range": f"bytes {start}-{end}/{all}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(end - start + 1),
            },
        )

    @error_decorator
    async def delete(self, file_path: Path) -> Union[Response, BaseModel]:
        if FileResolver.base_path not in file_path.parents:
            return self.not_allowed_response()
        elif FileResolver.temp_path == file_path:
            return self.not_allowed_response()
        elif FileResolver.temp_path in file_path.parents:
            return self.not_allowed_response()
        elif not await os.path.exists(file_path):
            return self.not_found_response()
        else:
            async with FileLockTransaction(SQLDepends.state, file_path):
                temp = await FileResolver.get_temp_from_data(file_path)
                if FileResolver.trashbin_path == file_path:
                    await shutil.rmtree(file_path)
                    await shutil.rmtree(temp)
                    await FileCRAD(self.session).delete(file_path)
                    await FileCRAD(self.session).delete(temp)
                    await os.makedirs(file_path)
                elif await FileCRAD(self.session).is_empty(file_path):
                    await shutil.rmtree(file_path)
                    await shutil.rmtree(temp)
                    await FileCRAD(self.session).delete(file_path)
                    await FileCRAD(self.session).delete(temp)
                elif FileResolver.trashbin_path in file_path.parents:
                    if await os.path.isdir(file_path):
                        await shutil.rmtree(file_path)
                        await shutil.rmtree(temp)
                        await FileCRAD(self.session).delete(file_path)
                        await FileCRAD(self.session).delete(temp)
                    else:
                        await os.remove(file_path)
                        await shutil.rmtree(temp)
                        await FileCRAD(self.session).delete(file_path)
                else:
                    trash = await FileResolver.get_trashbin_from_data(file_path)
                    temp_trash = await FileResolver.get_temp_from_data(trash)
                    await shutil.move(file_path, trash)
                    await shutil.move(temp, temp_trash)
                    await FileCRAD(self.session).move(file_path, trash)
                    await FileCRAD(self.session).move(temp, temp_trash)
            await self.session.commit()
            return self.success_response()

    @error_decorator
    async def mkdir(self, file_path: Path) -> Union[Response, BaseModel]:
        if FileResolver.base_path not in file_path.parents:
            return self.not_allowed_response()
        elif FileResolver.temp_path in file_path.parents:
            return self.not_allowed_response()
        elif FileResolver.trashbin_path in file_path.parents:
            return self.not_allowed_response()
        else:
            if await os.path.exists(file_path):
                return self.conflict_response()
            if not await os.path.isdir(file_path.parent):
                return self.not_allowed_response()

            await os.makedirs(file_path)
            return self.success_response()

    @error_decorator
    async def move(
        self, file_path: Path, rename_path: Path
    ) -> Union[Response, BaseModel]:
        if FileResolver.base_path not in file_path.parents:
            return self.not_allowed_response()
        elif FileResolver.base_path not in rename_path.parents:
            return self.not_allowed_response()
        elif FileResolver.temp_path in file_path.parents:
            return self.not_allowed_response()
        elif FileResolver.temp_path in rename_path.parents:
            return self.not_allowed_response()
        elif FileResolver.trashbin_path in rename_path.parents:
            return self.not_allowed_response()
        elif not await os.path.exists(file_path):
            return self.conflict_response()
        elif await os.path.exists(rename_path):
            return self.conflict_response()
        else:
            async with FileLockTransaction(SQLDepends.state, file_path):
                async with FileLockTransaction(SQLDepends.state, rename_path):
                    temp = await FileResolver.get_temp_from_data(file_path)
                    rename_temp = await FileResolver.get_temp_from_data(rename_path)
                    await shutil.move(file_path, rename_path)
                    await shutil.move(temp, rename_temp)
                    await FileCRAD(self.session).move(file_path, rename_path)
                    await FileCRAD(self.session).move(temp, rename_temp)
            await self.session.commit()
            return self.success_response()

    @error_decorator
    async def copy(
        self, file_path: Path, copy_path: Path
    ) -> Union[Response, BaseModel]:
        if FileResolver.base_path not in file_path.parents:
            return self.not_allowed_response()
        elif FileResolver.base_path not in copy_path.parents:
            return self.not_allowed_response()
        elif FileResolver.temp_path in file_path.parents:
            return self.not_allowed_response()
        elif FileResolver.temp_path in file_path.parents:
            return self.not_allowed_response()
        elif FileResolver.temp_path in copy_path.parents:
            return self.not_allowed_response()
        elif FileResolver.trashbin_path in copy_path.parents:
            return self.not_allowed_response()
        else:
            async with FileLockTransaction(SQLDepends.state, file_path):
                async with FileLockTransaction(SQLDepends.state, copy_path):
                    temp = await FileResolver.get_temp_from_data(file_path)
                    copy_temp = await FileResolver.get_temp_from_data(copy_path)
                    await shutil.copy2(file_path, copy_path)
                    await shutil.copy2(temp, copy_temp)
                    await FileCRAD(self.session).copy(file_path, copy_path)
                    await FileCRAD(self.session).copy(temp, copy_temp)
            await self.session.commit()
            return self.success_response()

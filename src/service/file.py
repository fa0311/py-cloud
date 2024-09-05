from logging import Logger
from pathlib import Path
from typing import Union

import aiofiles
import aiofiles.os as os
from fastapi import Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

import src.util.aioshutils as shutil
from src.job.slow_task import copy_hook, delete_hook, move_hook, put_hook
from src.util.file import FileResolver


class SuccessResponse(BaseModel):
    success: bool = True


class FileService:
    def success_response(self) -> Union[Response, BaseModel]:
        return JSONResponse(content={}, status_code=200)

    def data_response(self, data) -> Union[Response, BaseModel]:
        return JSONResponse(content=data, status_code=200)

    def conflict_response(self) -> Union[Response, BaseModel]:
        return JSONResponse(content={}, status_code=409)

    def not_allowed_response(self) -> Union[Response, BaseModel]:
        return JSONResponse(content={}, status_code=405)

    def not_found_response(self) -> Union[Response, BaseModel]:
        return JSONResponse(content={}, status_code=404)

    async def get_base(self, path: Path) -> list:
        return [
            {
                "response": {
                    "href": path.as_posix(),
                    "propstat": {
                        "prop": {},
                    },
                    "status": "HTTP/1.1 200 OK",
                }
            }
        ]

    async def get_file(self, href: Path, path: Path) -> Union[dict, BaseModel]:
        stat = await os.stat(path)
        content_type = await FileResolver.get_content_type(path)

        return {
            "response": {
                "href": href.as_posix(),
                "propstat": {
                    "prop": {
                        "getlastmodified": stat.st_mtime,
                        "getcontentlength": stat.st_size,
                        "resourcetype": None,
                        "getcontenttype": content_type,
                    },
                    "status": "HTTP/1.1 200 OK",
                },
            },
        }

    async def check(
        self,
        file_path: Path,
        request: Request,
        logger: Logger,
        session: AsyncSession,
    ) -> Union[Response, BaseModel]:
        if await os.path.exists(file_path):
            return self.success_response()
        else:
            return self.not_found_response()

    async def list(
        self,
        file_path: Path,
        request: Request,
        logger: Logger,
        session: AsyncSession,
    ) -> Union[Response, BaseModel]:
        if await os.path.isdir(file_path):
            responses = await self.get_base(Path(request.url.path))
            for file in await os.listdir(file_path.as_posix()):
                href = Path(request.url.path).joinpath(file)
                responses.append(await self.get_file(href, file_path.joinpath(file)))

            return self.data_response(responses)

        elif await os.path.isfile(file_path):
            href = Path(request.url.path)
            responses = [await self.get_file(href, file_path)]
            return self.data_response(responses)
        else:
            return self.not_found_response()

    async def upload(
        self,
        file_path: Path,
        request: Request,
        logger: Logger,
        session: AsyncSession,
    ) -> Union[Response, BaseModel]:
        # temp = await FileResolver.get_temp_from_data(file_path)
        if FileResolver.temp_path in file_path.parents:
            return self.not_allowed_response()
        else:
            binary_stream = request.stream()

            async with aiofiles.open(file_path, "wb") as f:
                async for chunk in binary_stream:
                    await f.write(chunk)

            if FileResolver.trashbin_path in file_path.parents:
                pass
            else:
                await put_hook(session, file_path)
            return self.success_response()

    async def download(
        self,
        file_path: Path,
        request: Request,
        logger: Logger,
        session: AsyncSession,
    ) -> Union[Response, BaseModel]:
        if await os.path.isfile(file_path):
            return FileResponse(file_path, media_type="application/octet-stream")
        else:
            return self.not_found_response()

    async def delete(
        self,
        file_path: Path,
        request: Request,
        logger: Logger,
        session: AsyncSession,
    ) -> Union[Response, BaseModel]:
        if FileResolver.temp_path in file_path.parents:
            return self.not_allowed_response()
        elif FileResolver.trashbin_path in file_path.parents:
            if await os.path.isdir(file_path):
                await shutil.rmtree(file_path)
            else:
                await os.remove(file_path)
        elif FileResolver.trashbin_path == file_path:
            await shutil.rmtree(file_path)
            await os.makedirs(file_path)
        else:
            trash = await FileResolver.get_trashbin_from_data(file_path)
            await shutil.move(file_path, trash)
            await delete_hook(session, file_path)
        return self.success_response()

    async def mkdir(
        self,
        file_path: Path,
        request: Request,
        logger: Logger,
        session: AsyncSession,
    ) -> Union[Response, BaseModel]:
        if FileResolver.temp_path in file_path.parents:
            return self.not_allowed_response()
        else:
            if await os.path.exists(file_path):
                return self.conflict_response()
            if not await os.path.isdir(file_path.parent):
                return self.not_allowed_response()

            await os.makedirs(file_path)
            return self.success_response()

    async def move(
        self,
        file_path: Path,
        rename_path: Path,
        request: Request,
        logger: Logger,
        session: AsyncSession,
    ) -> Union[Response, BaseModel]:
        if FileResolver.temp_path in file_path.parents:
            return self.not_allowed_response()
        elif FileResolver.temp_path in rename_path.parents:
            return self.not_allowed_response()
        elif not await os.path.exists(file_path):
            return self.conflict_response()
        elif await os.path.exists(rename_path):
            return self.conflict_response()
        else:
            await shutil.move(file_path, rename_path)
            path_trash = FileResolver.trashbin_path in file_path.parents
            rename_trash = FileResolver.trashbin_path in rename_path.parents

            if rename_trash and path_trash:
                pass
            elif rename_trash:
                await delete_hook(session, file_path)
            elif path_trash:
                await put_hook(session, rename_path)
            else:
                await move_hook(session, file_path, rename_path)
            return self.success_response()

    async def copy(
        self,
        file_path: Path,
        copy_path: Path,
        request: Request,
        logger: Logger,
        session: AsyncSession,
    ) -> Union[Response, BaseModel]:
        if FileResolver.temp_path in file_path.parents:
            return self.not_allowed_response()
        elif FileResolver.temp_path in copy_path.parents:
            return self.not_allowed_response()
        else:
            await shutil.copyfile(file_path, copy_path)
            path_trash = FileResolver.trashbin_path in file_path.parents
            copy_trash = FileResolver.trashbin_path in copy_path.parents

            if copy_trash:
                pass
            elif path_trash:
                await put_hook(session, copy_path)
            else:
                await copy_hook(session, file_path, copy_path)
            return self.success_response()

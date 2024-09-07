import asyncio
from hashlib import md5
from logging import Logger
from pathlib import Path
from typing import Union
from urllib.parse import quote

from aiofiles import open, os
from fastapi import Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from src.depends.sql import SQLDepends
from src.models.file import FileModel, FileORM
from src.models.slow_task import SlowTaskModel, SlowTaskORM
from src.sql.file_crad import FileCRAD
from src.sql.file_lock_crad import FileLockCRADError, FileLockTransaction
from src.sql.sql import escape_path
from src.util import aioshutils as shutil
from src.util.file import FileResolver
from src.util.rfc1123 import RFC1123


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
        file_state = select(FileORM).where(
            FileORM.filename.like(f"{escape_path(path)}%")
        )
        files = (await self.session.execute(file_state)).all()
        if files:
            quota_used_bytes = sum([x.tuple()[0].size for x in files])
            max_modified = max([x.tuple()[0].updated_at.timestamp() for x in files])
        else:
            stat = await os.stat(path)
            quota_used_bytes = stat.st_size
            max_modified = stat.st_mtime
        get_last_modified = RFC1123.fromtimestamp(max_modified).rfc_1123()
        return [
            {
                "response": {
                    "href": quote(href.as_posix() + "/"),
                    "propstat": {
                        "prop": {
                            "getlastmodified": get_last_modified,
                            "resourcetype": {"collection": None},
                            "quota-used-bytes": quota_used_bytes,
                            "quota-available-bytes": -3,
                            "getetag": md5(href.as_posix().encode()).hexdigest(),
                        },
                        "status": "HTTP/1.1 200 OK",
                    },
                },
            }
        ]

    async def get_file(self, href: Path, path: Path) -> Union[dict, BaseModel]:
        if await os.path.isdir(path):
            file_state = select(FileORM).where(
                FileORM.filename.like(f"{escape_path(path)}%")
            )
            files = (await self.session.execute(file_state)).all()
            if files:
                quota_used_bytes = sum([x.tuple()[0].size for x in files])
                max_modified = max([x.tuple()[0].updated_at.timestamp() for x in files])
            else:
                stat = await os.stat(path)
                quota_used_bytes = stat.st_size
                max_modified = stat.st_mtime

            get_last_modified = RFC1123.fromtimestamp(max_modified).rfc_1123()
            return {
                "response": {
                    "href": quote(href.as_posix() + "/"),
                    "propstat": {
                        "prop": {
                            "getlastmodified": get_last_modified,
                            "resourcetype": {"collection": None},
                            "quota-used-bytes": quota_used_bytes,
                            "quota-available-bytes": -3,
                            "getetag": hash(path),
                        },
                        "status": "HTTP/1.1 200 OK",
                    },
                },
            }
        elif await os.path.isfile(path):
            file_state = select(FileORM).where(FileORM.filename == str(path))
            (file_orm,) = (await self.session.execute(file_state)).one()
            assert isinstance(file_orm, FileORM)
            file_model = FileModel.model_validate_orm(file_orm)
            get_last_modified = RFC1123(file_model.updated_at).rfc_1123()
            get_content_length = file_model.size
            get_content_type = file_model.internet_media_type
            return {
                "response": {
                    "href": quote(href.as_posix()),
                    "propstat": {
                        "prop": {
                            "getlastmodified": get_last_modified,
                            "getcontentlength": get_content_length,
                            "resourcetype": {},
                            "getcontenttype": get_content_type,
                            "getetag": md5(href.as_posix().encode()).hexdigest(),
                        },
                        "status": "HTTP/1.1 200 OK",
                    },
                },
            }
        else:
            raise ValueError("Invalid file path")

    @error_decorator
    async def check(self, file_path: Path) -> Union[Response, BaseModel]:
        if await os.path.exists(file_path):
            return self.success_response()
        else:
            return self.not_found_response()

    @error_decorator
    async def lock(self, file_path: Path) -> Union[Response, BaseModel]:
        file_state = select(FileORM).where(FileORM.filename == str(file_path))
        (file_orm,) = (await self.session.execute(file_state)).one()
        assert isinstance(file_orm, FileORM)
        file_model = FileModel.model_validate_orm(file_orm)
        get_last_modified = RFC1123(file_model.updated_at).rfc_1123()
        get_content_length = file_model.size
        get_content_type = file_model.internet_media_type

        response = {
            "response": {
                "href": quote(file_path.as_posix()),
                "propstat": {
                    "prop": {
                        "lockdiscovery": {
                            "activelock": {
                                "locktype": "write",
                                "lockscope": "exclusive",
                                "depth": "0",
                                "owner": "owner",
                                "timeout": "Second-3600",
                                "locktoken": {
                                    "href": "urn:uuid:12345678-1234-1234-1234-123456789012"
                                },
                            }
                        },
                        "getlastmodified": get_last_modified,
                        "getcontentlength": get_content_length,
                        "resourcetype": {},
                        "getcontenttype": get_content_type,
                        "getetag": md5(file_path.as_posix().encode()).hexdigest(),
                    },
                    "status": "HTTP/1.1 200 OK",
                },
            },
        }
        return self.data_response(response)

    @error_decorator
    async def unlock(self, file_path: Path) -> Union[Response, BaseModel]:
        return self.no_content_response()

    @error_decorator
    async def list(self, file_path: Path) -> Union[Response, BaseModel]:
        if await os.path.isdir(file_path):
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
    async def upload(self, file_path: Path) -> Union[Response, BaseModel]:
        if FileResolver.temp_path in file_path.parents:
            return self.not_allowed_response()
        elif FileResolver.trashbin_path in file_path.parents:
            return self.not_allowed_response()
        elif await os.path.exists(file_path):
            return self.conflict_response()
        else:
            async with FileLockTransaction(SQLDepends.state, file_path):
                binary_stream = self.request.stream()
                async with open(file_path, "wb") as f:
                    async for chunk in binary_stream:
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

    async def stream(self, file_path: Path, start: int, end: int):
        try:
            async with open(file_path, "rb") as f:
                await f.seek(start)
                chunk_size = FileResponse.chunk_size
                while start < end:
                    chunk = await f.read(min(chunk_size, end - start + 1))
                    if not chunk:
                        break
                    start += len(chunk)
                    yield chunk
        except asyncio.CancelledError:
            pass

    @error_decorator
    async def download(
        self, file_path: Path
    ) -> Union[Response, BaseModel, StreamingResponse]:
        if not await os.path.isfile(file_path):
            return self.not_found_response()
        elif self.request.headers.get("Range"):
            start, end = self.request.headers["Range"].split("=")[1].split("-")
            start = int(start) if start else 0
            end = int(end) if end else await os.path.getsize(file_path) - 1
        else:
            start = 0
            end = await os.path.getsize(file_path) - 1

        return StreamingResponse(
            self.stream(file_path, start, end),
            headers={
                "Content-Range": f"bytes {start}-{end}/{await os.path.getsize(file_path)}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(end - start + 1),
            },
        )

    @error_decorator
    async def delete(self, file_path: Path) -> Union[Response, BaseModel]:
        if FileResolver.temp_path == file_path:
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
                    await os.makedirs(file_path)
                elif await FileCRAD(self.session).is_empty(file_path):
                    await shutil.rmtree(file_path)
                    await shutil.rmtree(temp)
                elif FileResolver.trashbin_path in file_path.parents:
                    if await os.path.isdir(file_path):
                        await shutil.rmtree(file_path)
                        await shutil.rmtree(temp)
                    else:
                        await os.remove(file_path)
                        await shutil.rmtree(temp)
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
        if FileResolver.temp_path in file_path.parents:
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
        if FileResolver.temp_path in file_path.parents:
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
        if FileResolver.temp_path in file_path.parents:
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

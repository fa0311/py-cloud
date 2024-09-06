from hashlib import md5
from logging import Logger
from pathlib import Path
from typing import Union
from urllib.parse import quote

import aiofiles
import aiofiles.os as os
from fastapi import Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

import src.util.aioshutils as shutil
from src.models.file import FileModel, FileORM
from src.service.metadata import (
    copy_hook,
    delete_hook,
    escape_path,
    move_hook,
    put_hook,
)
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

    async def check(self, file_path: Path) -> Union[Response, BaseModel]:
        if await os.path.exists(file_path):
            return self.success_response()
        else:
            return self.not_found_response()

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

    async def unlock(self, file_path: Path) -> Union[Response, BaseModel]:
        return self.no_content_response()

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

    async def upload(self, file_path: Path) -> Union[Response, BaseModel]:
        # temp = await FileResolver.get_temp_from_data(file_path)
        if FileResolver.temp_path in file_path.parents:
            return self.not_allowed_response()
        elif await os.path.exists(file_path):
            return self.conflict_response()
        else:
            binary_stream = self.request.stream()

            async with aiofiles.open(file_path, "wb") as f:
                async for chunk in binary_stream:
                    await f.write(chunk)

            if FileResolver.trashbin_path in file_path.parents:
                pass
            else:
                await put_hook(self.session, file_path)
            return self.created_response()

    async def download(self, file_path: Path) -> Union[Response, BaseModel]:
        if await os.path.isfile(file_path):
            return FileResponse(file_path, media_type="application/octet-stream")
        else:
            return self.not_found_response()

    async def delete(self, file_path: Path) -> Union[Response, BaseModel]:
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
            await delete_hook(self.session, file_path)
        return self.success_response()

    async def mkdir(self, file_path: Path) -> Union[Response, BaseModel]:
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
        self, file_path: Path, rename_path: Path
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
                await delete_hook(self.session, file_path)
            elif path_trash:
                await put_hook(self.session, rename_path)
            else:
                await move_hook(self.session, file_path, rename_path)
            return self.success_response()

    async def copy(
        self, file_path: Path, copy_path: Path
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
                await put_hook(self.session, copy_path)
            else:
                await copy_hook(self.session, file_path, copy_path)
            return self.success_response()

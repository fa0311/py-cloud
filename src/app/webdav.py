from hashlib import md5
from logging import Logger
from pathlib import Path
from typing import Union
from urllib.parse import quote

from aiofiles import os
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.models.file import FileModel, FileORM
from src.models.metadata import MetadataORM
from src.service.slow_task import FileService
from src.sql.file_crad import FileCRAD
from src.sql.sql import escape_path
from src.util.file import FileResolver
from src.util.rfc1123 import RFC1123
from src.util.xml import to_webdav

router = APIRouter()


class FileServiceWebDav(FileService):
    def success_response(self):
        return Response(media_type="application/octet-stream")

    def created_response(self):
        return Response(media_type="application/octet-stream", status_code=201)

    def no_content_response(self):
        return Response(media_type="application/octet-stream", status_code=204)

    def data_response(self, data):
        content = to_webdav(data)
        return Response(content=content, media_type="application/xml", status_code=207)

    def conflict_response(self):
        return Response(media_type="application/octet-stream", status_code=409)

    def not_allowed_response(self):
        return Response(media_type="application/octet-stream", status_code=405)

    def not_found_response(self):
        return Response(media_type="application/octet-stream", status_code=404)

    async def get_base(self, href: Path, path: Path) -> list:
        file_state = (
            select(FileORM, MetadataORM)
            .join(MetadataORM, MetadataORM.id == FileORM.metadata_id)
            .where(FileORM.filename.like(f"{escape_path(path)}%"))
        )
        files = (await self.session.execute(file_state)).all()
        if files:
            quota_used_bytes = sum([x.tuple()[1].size for x in files])
            max_modified = max([x.tuple()[1].created_at.timestamp() for x in files])
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

    async def get_file(self, href: Path, path: Path) -> Union[dict, BaseModel, None]:
        if await FileCRAD(self.session).isdir(path):
            file_state = (
                select(FileORM, MetadataORM)
                .join(MetadataORM, MetadataORM.id == FileORM.metadata_id)
                .where(FileORM.filename.like(f"{escape_path(path)}%"))
            )
            files = (await self.session.execute(file_state)).all()
            if files:
                quota_used_bytes = sum([x.tuple()[1].size for x in files])
                max_modified = max([x.tuple()[1].created_at.timestamp() for x in files])
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
        elif await FileCRAD(self.session).isfile(path):
            file_state = (
                select(FileORM, MetadataORM)
                .join(MetadataORM, MetadataORM.id == FileORM.metadata_id)
                .where(FileORM.filename == str(path))
            )
            first = (await self.session.execute(file_state)).first()
            if first:
                (file_orm, metadata_orm) = first.tuple()
                file_model = FileModel.model_validate_orm(file_orm)

                get_last_modified = RFC1123(file_model.created_at).rfc_1123()
                get_content_length = metadata_orm.size
                get_content_type = metadata_orm.internet_media_type
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
                return None
        else:
            return None

    @FileService.error_decorator
    async def check(self, file_path: Path) -> Union[Response, BaseModel]:
        if await FileCRAD(self.session).exists(file_path):
            return self.success_response()
        else:
            return self.not_found_response()

    @FileService.error_decorator
    async def lock(self, file_path: Path) -> Union[Response, BaseModel]:
        file_state = select(FileORM).where(FileORM.filename == str(file_path))
        (file_orm,) = (await self.session.execute(file_state)).one().tuple()
        file_model = FileModel.model_validate_orm(file_orm)
        get_last_modified = RFC1123(file_model.created_at).rfc_1123()

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
                        "resourcetype": {},
                        "getetag": md5(file_path.as_posix().encode()).hexdigest(),
                    },
                    "status": "HTTP/1.1 200 OK",
                },
            },
        }
        return self.data_response(response)

    @FileService.error_decorator
    async def unlock(self, file_path: Path) -> Union[Response, BaseModel]:
        return self.no_content_response()


@router.api_route(
    "/webdav/{file_path:path}",
    tags=["webdav"],
    methods=["HEAD", "OPTIONS", "PROPPATCH"],
    description="Check file in webdav",
)
async def check(
    file_path: str,
    request: Request,
    logger: Logger = Depends(LoggingDepends.depends),
    session: AsyncSession = Depends(SQLDepends.depends),
):
    path = await FileResolver.get_file(file_path)
    return await FileServiceWebDav(request, logger, session).check(path)


@router.api_route(
    "/webdav/{file_path:path}",
    tags=["webdav"],
    methods=["LOCK"],
    description="Lock file in webdav",
)
async def lock(
    file_path: str,
    request: Request,
    logger: Logger = Depends(LoggingDepends.depends),
    session: AsyncSession = Depends(SQLDepends.depends),
):
    path = await FileResolver.get_file(file_path)
    return await FileServiceWebDav(request, logger, session).lock(path)


@router.api_route(
    "/webdav/{file_path:path}",
    tags=["webdav"],
    methods=["UNLOCK"],
    description="Unlock file in webdav",
)
async def unlock(
    file_path: str,
    request: Request,
    logger: Logger = Depends(LoggingDepends.depends),
    session: AsyncSession = Depends(SQLDepends.depends),
):
    path = await FileResolver.get_file(file_path)
    return await FileServiceWebDav(request, logger, session).unlock(path)


@router.api_route(
    "/webdav/{file_path:path}",
    tags=["webdav"],
    methods=["PROPFIND"],
    description="List files in webdav",
)
async def list(
    file_path: str,
    request: Request,
    logger: Logger = Depends(LoggingDepends.depends),
    session: AsyncSession = Depends(SQLDepends.depends),
):
    path = await FileResolver.get_file(file_path)
    return await FileServiceWebDav(request, logger, session).list(path)


@router.api_route(
    "/webdav/{file_path:path}",
    tags=["webdav"],
    methods=["PUT"],
    description="Upload file to webdav",
)
async def upload(
    file_path: str,
    request: Request,
    logger: Logger = Depends(LoggingDepends.depends),
    session: AsyncSession = Depends(SQLDepends.depends),
):
    path = await FileResolver.get_file(file_path)
    stream = request.stream()
    return await FileServiceWebDav(request, logger, session).upload(path, stream)


@router.api_route(
    "/webdav/{file_path:path}",
    tags=["webdav"],
    methods=["GET"],
    description="Download file from webdav",
)
async def download(
    file_path: str,
    request: Request,
    logger: Logger = Depends(LoggingDepends.depends),
    session: AsyncSession = Depends(SQLDepends.depends),
):
    path = await FileResolver.get_file(file_path)
    return await FileServiceWebDav(request, logger, session).download(path)


@router.api_route(
    "/webdav/{file_path:path}",
    tags=["webdav"],
    methods=["DELETE"],
    description="Delete file from webdav",
)
async def delete(
    file_path: str,
    request: Request,
    logger: Logger = Depends(LoggingDepends.depends),
    session: AsyncSession = Depends(SQLDepends.depends),
):
    path = await FileResolver.get_file(file_path)
    return await FileServiceWebDav(request, logger, session).delete(path)


@router.api_route(
    "/webdav/{file_path:path}",
    tags=["webdav"],
    methods=["MKCOL"],
    description="Create directory in webdav",
)
async def mkdir(
    file_path: str,
    request: Request,
    logger: Logger = Depends(LoggingDepends.depends),
    session: AsyncSession = Depends(SQLDepends.depends),
):
    path = FileResolver.base_path.joinpath(file_path)
    return await FileServiceWebDav(request, logger, session).mkdir(path)


@router.api_route(
    "/webdav/{file_path:path}",
    tags=["webdav"],
    methods=["MOVE"],
    description="Move file in webdav",
)
async def move(
    file_path: str,
    request: Request,
    logger: Logger = Depends(LoggingDepends.depends),
    session: AsyncSession = Depends(SQLDepends.depends),
):
    path = await FileResolver.get_file(file_path)
    baseurl = FileResolver.get_base_url(Path(request.url.path), Path(file_path))
    rename = await FileResolver.from_url(baseurl, request.headers["destination"])
    return await FileServiceWebDav(request, logger, session).move(path, rename)


@router.api_route(
    "/webdav/{file_path:path}",
    tags=["webdav"],
    methods=["COPY"],
    description="Copy file in webdav",
)
async def copy(
    file_path: str,
    request: Request,
    logger: Logger = Depends(LoggingDepends.depends),
    session: AsyncSession = Depends(SQLDepends.depends),
):
    path = await FileResolver.get_file(file_path)
    baseurl = FileResolver.get_base_url(Path(request.url.path), Path(file_path))
    copy = await FileResolver.from_url(baseurl, request.headers["destination"])

    return await FileServiceWebDav(request, logger, session).copy(path, copy)

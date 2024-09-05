from logging import Logger
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPBasic
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.service.file import FileService
from src.util.file import FileResolver
from src.util.xml import to_webdav

security = HTTPBasic()
router = APIRouter()


class FileServiceWebDav(FileService):
    def success_response(self):
        return Response(media_type="application/octet-stream")

    def data_response(self, data):
        return Response(content=to_webdav(data), media_type="application/xml")

    def conflict_response(self):
        return Response(media_type="application/octet-stream", status_code=409)

    def not_allowed_response(self):
        return Response(media_type="application/octet-stream", status_code=405)

    def not_found_response(self):
        return Response(media_type="application/octet-stream", status_code=404)


@router.api_route(
    "/webdav/{file_path:path}",
    tags=["webdav"],
    methods=["HEAD", "OPTIONS", "LOCK", "UNLOCK", "PROPPATCH"],
    description="Check file in webdav",
)
async def check(
    file_path: str,
    request: Request,
    logger: Logger = Depends(LoggingDepends.depends),
    session: AsyncSession = Depends(SQLDepends.depends),
):
    path = await FileResolver.get_file(file_path)
    return await FileServiceWebDav().check(path, request, logger, session)


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
    return await FileServiceWebDav().list(path, request, logger, session)


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
    return await FileServiceWebDav().upload(path, request, logger, session)


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
    return await FileServiceWebDav().download(path, request, logger, session)


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
    return await FileServiceWebDav().delete(path, request, logger, session)


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
    return await FileServiceWebDav().mkdir(path, request, logger, session)


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
    return await FileServiceWebDav().move(path, rename, request, logger, session)


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

    return await FileServiceWebDav().copy(path, copy, request, logger, session)

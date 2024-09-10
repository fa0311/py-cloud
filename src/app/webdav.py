from hashlib import md5
from logging import Logger
from pathlib import Path
from typing import Union
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.models.file import FileModel, FileORM
from src.models.response import DirectoryResponseModel, FileResponseModel
from src.service.api import FileService
from src.sql.file_crad import FileCRAD
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

    def dir_to_json(self, file: DirectoryResponseModel):
        getetag = md5(file.file.filename.as_posix().encode()).hexdigest()
        resolve = file.file.filename.relative_to(FileResolver.base_path)
        baseurl = FileResolver.get_base_url(Path(self.request.url.path), resolve)
        if Path(self.request.url.path).relative_to(baseurl) == resolve:
            href = baseurl.joinpath(resolve)
        else:
            href = Path(self.request.url.path).joinpath(file.file.filename.name)

        return {
            "response": {
                "href": quote(href.as_posix() + "/"),
                "propstat": {
                    "prop": {
                        "getlastmodified": RFC1123(file.file.created_at).rfc_1123(),
                        "resourcetype": {"collection": None},
                        "quota-used-bytes": file.size,
                        "quota-available-bytes": -3,
                        "getetag": getetag,
                    },
                    "status": "HTTP/1.1 200 OK",
                },
            },
        }

    def file_to_json(self, file: FileResponseModel):
        getetag = md5(file.file.filename.as_posix().encode()).hexdigest()
        resolve = file.file.filename.relative_to(FileResolver.base_path)
        baseurl = FileResolver.get_base_url(Path(self.request.url.path), resolve)
        if Path(self.request.url.path).relative_to(baseurl) == resolve:
            href = baseurl.joinpath(resolve)
        else:
            href = Path(self.request.url.path).joinpath(file.file.filename.name)
        return {
            "response": {
                "href": quote(href.as_posix()),
                "propstat": {
                    "prop": {
                        "getlastmodified": RFC1123(file.file.created_at).rfc_1123(),
                        "getcontentlength": file.metadata.size,
                        "resourcetype": {},
                        "getcontenttype": file.metadata.internet_media_type,
                        "getetag": getetag,
                    },
                    "status": "HTTP/1.1 200 OK",
                },
            },
        }

    async def get_dir(self, file_path: Path):
        dir = await FileCRAD(self.session).getdir(file_path)
        res = [self.dir_to_json(dir)]
        for file in await FileCRAD(self.session).listdir(file_path):
            if file.directory:
                data = await FileCRAD(self.session).getdir(file.filename)
                res.append(self.dir_to_json(data))
            else:
                data = await FileCRAD(self.session).getfile(file.filename)
                res.append(self.file_to_json(data))

        return self.data_response(res)

    async def get_file(self, file_path: Path):
        file = await FileCRAD(self.session).getfile(file_path)
        return self.data_response([self.file_to_json(file)])

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
    path = FileResolver.get_file(file_path)
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
    path = FileResolver.get_file(file_path)
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
    path = FileResolver.get_file(file_path)
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
    path = FileResolver.get_file(file_path)
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
    path = FileResolver.get_file(file_path)
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
    path = FileResolver.get_file(file_path)
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
    path = FileResolver.get_file(file_path)
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
    path = FileResolver.get_file(file_path)
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
    path = FileResolver.get_file(file_path)
    baseurl = FileResolver.get_base_url(Path(request.url.path), Path(file_path))
    copy = await FileResolver.from_url(baseurl, request.headers["destination"])

    return await FileServiceWebDav(request, logger, session).copy(path, copy)

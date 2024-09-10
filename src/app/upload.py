from logging import Logger
from pathlib import Path
from typing import Annotated, Union
from urllib.parse import quote

import aiofiles.os as os
from aiofiles import open
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.models.file import FileORM
from src.models.metadata import MetadataORM
from src.service.slow_task import FileService
from src.sql.file_crad import FileCRAD
from src.sql.sql import escape_path, sep
from src.util.rfc1123 import RFC1123
from src.util.stream import Stream

router = APIRouter()


class SuccessResponse(BaseModel):
    success: bool = True


class DirectoryResponse(BaseModel):
    href: str
    get_last_modified: str
    quota_used_bytes: int


class FileServiceRest(FileService):
    def success_response(self):
        return SuccessResponse()

    def data_response(self, data: BaseModel):
        return data

    def conflict_response(self):
        raise HTTPException(status_code=409)

    def not_allowed_response(self):
        raise HTTPException(status_code=405)

    def not_found_response(self):
        raise HTTPException(status_code=404)

    async def get_base(self, href: Path, path: Path) -> list:
        return []

    async def get_file(self, href: Path, path: Path) -> Union[DirectoryResponse, None]:
        if await FileCRAD(self.session).isdir(path):
            file_state = (
                select(FileORM, MetadataORM)
                .join(MetadataORM, MetadataORM.id == FileORM.metadata_id)
                .where(FileORM.filename.like(f"{escape_path(path)}{sep}%"))
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
            return DirectoryResponse(
                href=quote(href.as_posix()),
                get_last_modified=get_last_modified,
                quota_used_bytes=quota_used_bytes,
            )
        elif await FileCRAD(self.session).isfile(path):
            file_state = (
                select(FileORM, MetadataORM)
                .join(MetadataORM, MetadataORM.id == FileORM.metadata_id)
                .where(FileORM.filename == str(path))
            )
            first = (await self.session.execute(file_state)).first()
            if first:
                metadata = first.tuple()[1]
                get_last_modified = RFC1123.fromtimestamp(
                    metadata.created_at.timestamp()
                ).rfc_1123()

                return DirectoryResponse(
                    href=quote(href.as_posix()),
                    get_last_modified=get_last_modified,
                    quota_used_bytes=metadata.size,
                )
            else:
                return None
        else:
            return None

    async def read_file(self, path: Path):
        async with open(path, "rb") as file:
            return await file.read()


def stream(file: UploadFile):
    while True:
        chunk = file.file.read(1024)
        if not chunk:
            break
        yield chunk


@router.get(
    "/list/{file_path:path}",
    operation_id="get_list",
    tags=["list"],
    description="list",
)
async def get_list(
    file_path: str,
    request: Request,
    logger: Annotated[Logger, Depends(LoggingDepends.depends)],
    session: Annotated[AsyncSession, Depends(SQLDepends.depends)],
):
    path = Path(file_path)
    return await FileServiceRest(request, logger, session).list(path)


@router.put(
    "/upload/{file_path:path}",
    operation_id="post_upload",
    tags=["upload"],
    description="upload",
)
async def post_upload(
    file_path: str,
    file: UploadFile,
    request: Request,
    logger: Annotated[Logger, Depends(LoggingDepends.depends)],
    session: Annotated[AsyncSession, Depends(SQLDepends.depends)],
):
    path = Path(file_path)
    stream = Stream.read(file, 0, None)
    return await FileServiceRest(request, logger, session).upload(path, stream)


@router.get(
    "/download/{file_path:path}",
    operation_id="get_download",
    tags=["download"],
    description="download",
)
async def get_download(
    file_path: str,
    request: Request,
    logger: Annotated[Logger, Depends(LoggingDepends.depends)],
    session: Annotated[AsyncSession, Depends(SQLDepends.depends)],
):
    path = Path(file_path)
    return await FileServiceRest(request, logger, session).download(path)


@router.delete(
    "/delete/{file_path:path}",
    operation_id="delete_delete",
    tags=["delete"],
    description="delete",
)
async def delete_delete(
    file_path: str,
    request: Request,
    logger: Annotated[Logger, Depends(LoggingDepends.depends)],
    session: Annotated[AsyncSession, Depends(SQLDepends.depends)],
):
    path = Path(file_path)
    return await FileServiceRest(request, logger, session).delete(path)


@router.post(
    "/mkdir/{file_path:path}",
    operation_id="post_mkdir",
    tags=["mkdir"],
    description="mkdir",
)
async def post_mkdir(
    file_path: str,
    request: Request,
    logger: Annotated[Logger, Depends(LoggingDepends.depends)],
    session: Annotated[AsyncSession, Depends(SQLDepends.depends)],
):
    path = Path(file_path)
    return await FileServiceRest(request, logger, session).mkdir(path)


@router.post(
    "/move/{file_path:path}",
    operation_id="post_move",
    tags=["move"],
    description="move",
)
async def post_move(
    file_path: str,
    rename_path: str,
    request: Request,
    logger: Annotated[Logger, Depends(LoggingDepends.depends)],
    session: Annotated[AsyncSession, Depends(SQLDepends.depends)],
):
    path = Path(file_path)
    rename = Path(rename_path)
    return await FileServiceRest(request, logger, session).move(path, rename)


@router.post(
    "/copy/{file_path:path}",
    operation_id="post_copy",
    tags=["copy"],
    description="copy",
)
async def post_copy(
    file_path: str,
    copy_path: str,
    request: Request,
    logger: Annotated[Logger, Depends(LoggingDepends.depends)],
    session: Annotated[AsyncSession, Depends(SQLDepends.depends)],
):
    path = Path(file_path)
    copy = Path(copy_path)
    return await FileServiceRest(request, logger, session).copy(path, copy)

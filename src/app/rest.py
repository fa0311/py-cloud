from logging import Logger
from pathlib import Path
from typing import Annotated, Union

from aiofiles import open
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.models.response import DirectoryResponseModel, FileResponseModel
from src.service.api import FileService
from src.sql.file_crad import FileCRAD
from src.util.file import FileResolver
from src.util.stream import Stream

router = APIRouter()


class FileResponse(BaseModel):
    dir: DirectoryResponseModel
    child: list[Union[DirectoryResponseModel, FileResponseModel]]


class ResponseStatus(BaseModel):
    status: str


class FileServiceRest(FileService):
    def success_response(self):
        return ResponseStatus(status="success")

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

    async def read_file(self, path: Path):
        async with open(path, "rb") as file:
            return await file.read()

    async def get_dir(self, file_path: Path):
        dir = await FileCRAD(self.session).getdir(file_path)
        res = []
        for file in await FileCRAD(self.session).listdir(file_path):
            if file.directory:
                data = await FileCRAD(self.session).getdir(file.filename)
                res.append(data)
            else:
                data = await FileCRAD(self.session).getfile(file.filename)
                res.append(data)
        model = FileResponse(dir=dir, child=res)
        return self.data_response(model)

    async def get_file(self, file_path: Path):
        return self.not_found_response()


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
    responses={200: {"model": FileResponse}},
)
async def get_list(
    file_path: str,
    request: Request,
    logger: Annotated[Logger, Depends(LoggingDepends.depends)],
    session: Annotated[AsyncSession, Depends(SQLDepends.depends)],
):
    path = FileResolver.base_path.joinpath(file_path)
    return await FileServiceRest(request, logger, session).list(path)


@router.put(
    "/upload/{file_path:path}",
    operation_id="post_upload",
    tags=["upload"],
    description="upload",
    responses={200: {"model": ResponseStatus}},
)
async def post_upload(
    file_path: str,
    file: UploadFile,
    request: Request,
    logger: Annotated[Logger, Depends(LoggingDepends.depends)],
    session: Annotated[AsyncSession, Depends(SQLDepends.depends)],
):
    path = FileResolver.base_path.joinpath(file_path)
    stream = Stream.read(file, 0, None)
    return await FileServiceRest(request, logger, session).upload(path, stream)


@router.get(
    "/download/{file_path:path}",
    operation_id="get_download",
    tags=["download"],
    description="download",
    responses={200: {"model": bytes}},
)
async def get_download(
    file_path: str,
    request: Request,
    logger: Annotated[Logger, Depends(LoggingDepends.depends)],
    session: Annotated[AsyncSession, Depends(SQLDepends.depends)],
):
    path = FileResolver.base_path.joinpath(file_path)
    return await FileServiceRest(request, logger, session).download(path)


@router.delete(
    "/delete/{file_path:path}",
    operation_id="delete_delete",
    tags=["delete"],
    description="delete",
    responses={200: {"model": ResponseStatus}},
)
async def delete_delete(
    file_path: str,
    request: Request,
    logger: Annotated[Logger, Depends(LoggingDepends.depends)],
    session: Annotated[AsyncSession, Depends(SQLDepends.depends)],
):
    path = FileResolver.base_path.joinpath(file_path)
    return await FileServiceRest(request, logger, session).delete(path)


@router.post(
    "/mkdir/{file_path:path}",
    operation_id="post_mkdir",
    tags=["mkdir"],
    description="mkdir",
    responses={200: {"model": ResponseStatus}},
)
async def post_mkdir(
    file_path: str,
    request: Request,
    logger: Annotated[Logger, Depends(LoggingDepends.depends)],
    session: Annotated[AsyncSession, Depends(SQLDepends.depends)],
):
    path = FileResolver.base_path.joinpath(file_path)
    return await FileServiceRest(request, logger, session).mkdir(path)


@router.post(
    "/move/{file_path:path}",
    operation_id="post_move",
    tags=["move"],
    description="move",
    responses={200: {"model": ResponseStatus}},
)
async def post_move(
    file_path: str,
    rename_path: str,
    request: Request,
    logger: Annotated[Logger, Depends(LoggingDepends.depends)],
    session: Annotated[AsyncSession, Depends(SQLDepends.depends)],
):
    path = FileResolver.base_path.joinpath(file_path)
    rename = FileResolver.base_path.joinpath(rename_path)
    return await FileServiceRest(request, logger, session).move(path, rename)


@router.post(
    "/copy/{file_path:path}",
    operation_id="post_copy",
    tags=["copy"],
    description="copy",
    responses={200: {"model": ResponseStatus}},
)
async def post_copy(
    file_path: str,
    copy_path: str,
    request: Request,
    logger: Annotated[Logger, Depends(LoggingDepends.depends)],
    session: Annotated[AsyncSession, Depends(SQLDepends.depends)],
):
    path = FileResolver.base_path.joinpath(file_path)
    copy = FileResolver.base_path.joinpath(copy_path)
    return await FileServiceRest(request, logger, session).copy(path, copy)

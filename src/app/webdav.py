from logging import Logger
from pathlib import Path

import aiofiles
import aiofiles.os as os
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

import src.util.aioshutils as shutil
from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.job.slow_task import copy_hook, delete_hook, move_hook, put_hook
from src.util.file import FileResolver
from src.util.xml import to_webdav

security = HTTPBasic()
router = APIRouter()


def success_response():
    return Response(media_type="application/octet-stream")


def xml_response(xml):
    return Response(content=to_webdav(xml), media_type="application/xml")


def conflict_response():
    return Response(media_type="application/octet-stream", status_code=409)


def not_allowed_response():
    return Response(media_type="application/octet-stream", status_code=405)


def not_found_response():
    return Response(media_type="application/octet-stream", status_code=404)


def get_base(path: Path) -> list:
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


async def get_file(href: Path, path: Path):
    stat = await os.stat(path)

    if await os.path.isdir(path):
        content_type = "httpd/unix-directory"
    else:
        content_type = "application/octet-stream"

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

    if await os.path.exists(path):
        return success_response()
    else:
        return not_found_response()


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

    if await os.path.isdir(path):
        responses = get_base(Path(request.url.path))
        for file in await os.listdir(path.as_posix()):
            href = Path(request.url.path).joinpath(file)
            responses.append(await get_file(href, path.joinpath(file)))

        return xml_response(responses)

    elif await os.path.isfile(path):
        href = Path(request.url.path)
        responses = [await get_file(href, path)]
        return xml_response(responses)
    else:
        return not_found_response()


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
    if FileResolver.temp_path in Path(file_path).parents:
        return not_allowed_response()
    else:
        binary_stream = request.stream()
        output_file = await FileResolver.get_file(file_path)

        async with aiofiles.open(output_file, "wb") as f:
            async for chunk in binary_stream:
                await f.write(chunk)

        await put_hook(session, output_file)
        return success_response()


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

    if await os.path.isfile(path):
        return FileResponse(path, media_type="application/octet-stream")
    else:
        return not_found_response()


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

    if FileResolver.trashbin_path in path.parents:
        try:
            await shutil.rmtree(path)
        except Exception:
            return conflict_response()
        return success_response()

    elif FileResolver.temp_path in path.parents:
        return not_allowed_response()
    else:
        trash = await FileResolver.get_trashbin(file_path)

        try:
            await shutil.move(path, trash)
        except Exception:
            return conflict_response()

        await delete_hook(session, path)
        return success_response()


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
    if FileResolver.temp_path in path.parents:
        return not_allowed_response()
    else:
        if await os.path.exists(path):
            return conflict_response()

        await os.makedirs(path)
        return success_response()


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
    baseurl = FileResolver.get_base_url(Path(file_path), Path(request.url.path))
    rename = await FileResolver.from_url(baseurl, request.headers["destination"])

    if FileResolver.temp_path in path.parents:
        return not_allowed_response()
    elif FileResolver.temp_path in rename.parents:
        return not_allowed_response()
    elif FileResolver.trashbin_path in path.parents:
        return not_allowed_response()
    elif FileResolver.trashbin_path in rename.parents:
        return not_allowed_response()
    else:
        try:
            await shutil.move(path, rename)
        except Exception:
            return conflict_response()

        await move_hook(session, path, rename)
        return success_response()


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
    rename = await FileResolver.from_url(baseurl, request.headers["destination"])

    if FileResolver.temp_path in path.parents:
        return not_allowed_response()
    elif FileResolver.temp_path in rename.parents:
        return not_allowed_response()
    elif FileResolver.trashbin_path in path.parents:
        return not_allowed_response()
    elif FileResolver.trashbin_path in rename.parents:
        return not_allowed_response()
    else:
        try:
            await shutil.copyfile(path, rename)
        except Exception:
            return conflict_response()

        await copy_hook(session, path, rename)
        return success_response()

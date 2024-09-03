import time
from logging import Logger

import aiofiles
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.util.file import FileResolver
from src.util.xml import to_webdav

router = APIRouter()


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
    session: Session = Depends(SQLDepends.depends),
):
    responses = [
        {
            "response": {
                "href": "/api/webdav/",
                "propstat": {
                    "prop": {
                        "getlastmodified": time.strftime("%a, %d %b %Y %H:%M:%S GMT"),
                        "resourcetype": {"collection": None},
                        "quota-used-bytes": "861483204253",
                        "quota-available-bytes": "-3",
                    },
                    "status": "HTTP/1.1 200 OK",
                },
            },
        },
        {
            "response": {
                "href": "/api/webdav/test.txt",
                "propstat": {
                    "prop": {
                        "getlastmodified": time.strftime("%a, %d %b %Y %H:%M:%S GMT"),
                        "getcontentlength": str(1145141919810364364),
                        "resourcetype": None,
                        "getcontenttype": "application/octet-stream",
                    },
                    "status": "HTTP/1.1 200 OK",
                },
            },
        },
    ]

    output = to_webdav(responses)

    with open("output.xml", "w") as f:
        f.write(output.decode())

    return Response(
        content=to_webdav(responses),
        media_type="text/xml",
        headers={"Content-Type": "text/xml; charset=utf-8"},
    )


@router.api_route(
    "/webdav/{file_path:path}",
    tags=["webdav"],
    methods=["HEAD"],
    description="Check file in webdav",
)
async def check(
    file_path: str,
    request: Request,
    logger: Logger = Depends(LoggingDepends.depends),
    session: Session = Depends(SQLDepends.depends),
):
    return Response(
        content="",
        media_type="text/plain",
    )


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
    session: Session = Depends(SQLDepends.depends),
):
    try:
        binary_data = await request.body()
        output_file = await FileResolver.get_file_str(file_path)

        async with aiofiles.open(output_file, "wb") as f:
            await f.write(binary_data)

    except Exception as e:
        return Response(
            content=str(e),
            media_type="text/plain",
            status_code=500,
        )

    return Response(
        content="",
        media_type="text/plain",
    )

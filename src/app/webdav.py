from logging import Logger

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.util.xml import to_webdav

router = APIRouter()


@router.api_route(
    "/webdav/{file_path:path}",
    tags=["webdav"],
    methods=["PROPFIND"],
    description="List files in webdav",
)
def list(
    logger: Logger = Depends(LoggingDepends.depends),
    session: Session = Depends(SQLDepends.depends),
):
    responses = {
        "response": [
            {
                "href": "/remote.php/dav/files/yuki/",
                "prop": {},
                "status": "HTTP/1.1 200 OK",
            }
        ]
    }

    return Response(
        content=to_webdav(responses),
        media_type="text/xml",
    )


@router.api_route(
    "/webdav/{file_path:path}",
    tags=["webdav"],
    methods=["HEAD"],
    description="Check file in webdav",
)
def check(
    logger: Logger = Depends(LoggingDepends.depends),
    session: Session = Depends(SQLDepends.depends),
):
    return Response(
        content="",
        media_type="text/plain",
    )


# @router.api_route(
#     "/webdav/{file_path:path}",
#     tags=["webdav"],
#     methods=["HEAD"],
#     description="Upload file to webdav",
# )
# def upload(
#     file: bytes,
#     logger: Logger = Depends(LoggingDepends.depends),
#     session: Session = Depends(SQLDepends.depends),
# ):
#     return Response(
#         content="",
#         media_type="text/plain",
#     )

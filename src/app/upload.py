from logging import Logger

from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session

from depends.logging import LoggingDepends
from depends.sql import SQLDepends

router = APIRouter()


@router.put(
    "/api/upload",
    operation_id="put_upload",
    tags=["upload"],
    description="upload",
)
def put_upload(
    file: UploadFile = File(...),
    logger: Logger = Depends(LoggingDepends.depends),
    session: Session = Depends(SQLDepends.depends),
):
    pass

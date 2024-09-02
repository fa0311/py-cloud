import shutil
from logging import Logger

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.models.file import FileModel, FileORM
from src.models.slow_task import SlowTaskModel, SlowTaskORM
from src.util.ffmpeg import FFmpegWrapper
from src.util.file import FileResolver

router = APIRouter()


@router.post(
    "/upload/{file_path:path}",
    operation_id="post_upload",
    tags=["upload"],
    description="upload",
)
def post_upload(
    file_path: str,
    file: UploadFile = File(),
    logger: Logger = Depends(LoggingDepends.depends),
    session: Session = Depends(SQLDepends.depends),
):
    output_file = FileResolver.get_file_str(file_path)
    with output_file.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        ffmpeg = FFmpegWrapper.from_file(output_file)
        file_model = FileModel(
            filename=output_file,
            size=output_file.stat().st_size,
            directory=False,
            data={
                "ffprobe": ffmpeg.ffprobe,
            },
        )
        session.add(FileORM.from_model(file_model))

        if ffmpeg.is_video():
            task_model = SlowTaskModel(type="video_convert", file_id=file_model.id)
            session.add(SlowTaskORM.from_model(task_model))

        session.commit()

    except Exception:
        output_file.unlink()

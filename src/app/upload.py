import pathlib
import shutil
from logging import Logger

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.models.file import FileModel, FileORM
from src.models.slow_task import SlowTaskModel, SlowTaskORM
from src.util.ffmpeg import FFmpegWrapper

router = APIRouter()


class FileResolver:
    base_path = pathlib.Path("./data/data")
    temp_path = pathlib.Path("./data/temp")

    @staticmethod
    def get_file(file_path: str) -> pathlib.Path:
        file = FileResolver.base_path.joinpath(file_path)
        file.parent.mkdir(parents=True, exist_ok=True)
        return file

    @staticmethod
    def get_temp(file_path: str) -> pathlib.Path:
        temp = FileResolver.temp_path.joinpath(file_path)
        temp.mkdir(parents=True, exist_ok=True)
        return temp


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
    output_file = FileResolver.get_file(file_path)
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
            task_model = SlowTaskModel(name="video_convert", file_id=file_model.id)
            session.add(SlowTaskORM.from_model(task_model))

        session.commit()

    except Exception:
        output_file.unlink()

    # video = FFmpegWrapper(output_file)

    # temp_dir = FileResolver.get_temp(file_path)

    # if video.is_video():
    #     temp_dir = FileResolver.get_temp(file_path)

    #     if not video.check(640, 1000):
    #         video.hls(
    #             temp_dir,
    #             prefix="video_low",
    #             width=640,
    #             bitrate=250,
    #         )

    #     if not video.check(1280, 2000):
    #         video.hls(
    #             temp_dir,
    #             prefix="video_mid",
    #             width=1280,
    #             bitrate=500,
    #         )

    #     if not video.check(1920, 4000):
    #         video.hls(
    #             temp_dir,
    #             prefix="video_high",
    #             width=1920,
    #             bitrate=1000,
    #         )

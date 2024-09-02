from sqlalchemy.orm import Session
from sqlalchemy.sql import select

from src.app.upload import FileResolver
from src.depends.sql import SQLDepends
from src.models.file import FileModel, FileORM
from src.models.slow_task import SlowTaskModel, SlowTaskORM
from src.util.ffmpeg import FFmpegVideo


def slow_task():
    with Session(SQLDepends.state) as session:
        task_state = select(SlowTaskORM).where(SlowTaskORM.type == "video_convert")

        for (task_orm,) in session.execute(task_state).all():
            slow_task = SlowTaskModel.model_validate_orm(task_orm)

            file_state = select(FileORM).where(FileORM.id == str(slow_task.file_id))
            (file_orm,) = session.execute(file_state).one()
            file_model = FileModel.model_validate_orm(file_orm)

            ffmpeg = FFmpegVideo(
                input_file=file_model.filename,
                ffprobe=file_model.data["ffprobe"],
            )
            temp_dir = FileResolver.get_temp(file_model.filename)

            if not ffmpeg.check(640, 1000):
                ffmpeg.down_scale(
                    temp_dir,
                    prefix="video_low",
                    width=640,
                    bitrate=250,
                )

            if not ffmpeg.check(1280, 2000):
                ffmpeg.down_scale(
                    temp_dir,
                    prefix="video_mid",
                    width=1280,
                    bitrate=500,
                )

            if not ffmpeg.check(1920, 4000):
                ffmpeg.down_scale(
                    temp_dir,
                    prefix="video_high",
                    width=1920,
                    bitrate=1000,
                )

            ffmpeg.thumbnail(
                temp_dir,
                prefix="thumbnail",
            )

            session.delete(task_orm)
            session.commit()

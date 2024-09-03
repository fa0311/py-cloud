from sqlalchemy.ext.asyncio import (
    AsyncSession,
)
from sqlalchemy.sql import select

from src.depends.sql import SQLDepends
from src.models.file import FileModel, FileORM
from src.models.slow_task import SlowTaskModel, SlowTaskORM
from src.util.ffmpeg import FFmpegVideo
from src.util.file import FileResolver


async def slow_task():
    async with AsyncSession(SQLDepends.state) as session:
        task_state = select(SlowTaskORM).where(SlowTaskORM.type == "video_convert")

        for (task_orm,) in (await session.execute(task_state)).all():
            slow_task = SlowTaskModel.model_validate_orm(task_orm)

            file_state = select(FileORM).where(FileORM.id == str(slow_task.file_id))
            (file_orm,) = (await session.execute(file_state)).one()
            file_model = FileModel.model_validate_orm(file_orm)

            ffmpeg = FFmpegVideo(
                input_file=file_model.filename,
                ffprobe=file_model.data["ffprobe"],
            )
            temp_dir = await FileResolver.get_temp(file_model.filename)

            if not ffmpeg.check(640, 1000):
                await ffmpeg.down_scale(
                    temp_dir,
                    prefix="video_low",
                    width=640,
                    bitrate=250,
                )

            if not ffmpeg.check(1280, 2000):
                await ffmpeg.down_scale(
                    temp_dir,
                    prefix="video_mid",
                    width=1280,
                    bitrate=500,
                )

            if not ffmpeg.check(1920, 4000):
                await ffmpeg.down_scale(
                    temp_dir,
                    prefix="video_high",
                    width=1920,
                    bitrate=1000,
                )

            await ffmpeg.thumbnail(
                temp_dir,
                prefix="thumbnail",
            )

            await session.delete(task_orm)
            await session.commit()

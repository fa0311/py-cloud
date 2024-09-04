import shutil
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
)
from sqlalchemy.sql import select

from src.depends.sql import SQLDepends
from src.models.file import FileModel, FileORM
from src.models.slow_task import SlowTaskModel, SlowTaskORM
from src.util.ffmpeg import FFmpegVideo, FFmpegWrapper
from src.util.file import FileResolver


def escape_path(path: Path):
    return str(path).replace("\\", "\\\\")


async def put_hook(session: AsyncSession, file: Path):
    ffmpeg = await FFmpegWrapper.from_file(file)
    file_model = FileModel(
        filename=file,
        size=file.stat().st_size,
        directory=False,
        data={
            "ffprobe": ffmpeg.ffprobe,
        },
    )
    session.add(FileORM.from_model(file_model))

    if ffmpeg.is_video():
        task_model = SlowTaskModel(type="video_convert", file_id=file_model.id)
        session.add(SlowTaskORM.from_model(task_model))

    await session.commit()


async def delete_hook(session: AsyncSession, file: Path):
    file_state = select(FileORM).where(FileORM.filename.like(f"{escape_path(file)}%"))
    for (file_orm,) in (await session.execute(file_state)).all():
        await session.delete(file_orm)
    await session.commit()


async def move_hook(session: AsyncSession, src: Path, dst: Path):
    file_state = select(FileORM).where(FileORM.filename.like(f"{escape_path(src)}%"))
    for (file_orm,) in (await session.execute(file_state)).all():
        assert isinstance(file_orm, FileORM)
        file_model = FileModel.model_validate_orm(file_orm)
        dst_path = dst.joinpath(file_model.filename.relative_to(src))
        file_orm.filename = dst_path.as_posix()
    await session.commit()


async def copy_hook(session: AsyncSession, src: Path, dst: Path):
    file_state = select(FileORM).where(FileORM.filename.like(f"{escape_path(src)}%"))
    for (file_orm,) in (await session.execute(file_state)).all():
        file_model = FileModel.model_validate_orm(file_orm)
        dst_path = dst.joinpath(file_model.filename.relative_to(src))
        new_model = file_model.model_copy(
            update={
                "id": uuid.uuid4(),
                "filename": dst_path,
            }
        )
        session.add(FileORM.from_model(new_model))
    await session.commit()


async def slow_task():
    async with AsyncSession(SQLDepends.state) as session:
        task_state = select(SlowTaskORM).where(SlowTaskORM.type == "video_convert")

        for (task_orm,) in (await session.execute(task_state)).all():
            slow_task = SlowTaskModel.model_validate_orm(task_orm)

            file_state = select(FileORM).where(FileORM.id == str(slow_task.file_id))
            task_res = (await session.execute(file_state)).all()

            if len(task_res) > 0:
                (file_orm,) = task_res[0]

                file_model = FileModel.model_validate_orm(file_orm)

                ffmpeg = FFmpegVideo(
                    input_file=file_model.filename,
                    ffprobe=file_model.data["ffprobe"],
                )
                temp_dir = await FileResolver.get_temp_from_data(file_model.filename)

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

                for (other_orm,) in task_res[1:]:
                    other_file = FileModel.model_validate_orm(other_orm)
                    other_temp = await FileResolver.get_temp_from_data(
                        other_file.filename
                    )
                    await shutil.copy(temp_dir, other_temp)
                    await session.delete(other_orm)

            await session.delete(task_orm)
            await session.commit()

import uuid
from datetime import datetime
from pathlib import Path

import aiofiles.os as os
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)
from sqlalchemy.sql import select

from src.models.file import FileModel, FileORM
from src.models.slow_task import SlowTaskModel, SlowTaskORM
from src.util.aiometadata import (
    get_iptc_info,
    get_media_info,
    get_mutagen_metadata,
    get_pillow_metadata,
)
from src.util.ffmpeg import FFmpegWrapper


def escape_path(path: Path):
    return str(path).replace("\\", "\\\\")


async def put_hook(session: AsyncSession, file: Path, slow_task: bool = True):
    ffmpeg = await FFmpegWrapper.from_file(file)
    media_info = await get_media_info(file)
    size = await os.stat(file)
    file_model = FileModel(
        filename=file,
        size=size.st_size,
        directory=False,
        data={
            "ffprobe": ffmpeg.ffprobe,
            "media_info": media_info,
            "mutagen": await get_mutagen_metadata(file),
            "pillow": await get_pillow_metadata(file),
            "iptc_info": await get_iptc_info(file),
        },
        internet_media_type=media_info.get(
            "internet_media_type", "application/octet-stream"
        ),
    )
    session.add(FileORM.from_model(file_model))

    if ffmpeg.is_video() and slow_task:
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
        file_orm.updated_at = datetime.now()
        file_orm.filename = str(dst_path)
    await session.commit()


async def copy_hook(session: AsyncSession, src: Path, dst: Path):
    file_state = select(FileORM).where(FileORM.filename.like(f"{escape_path(src)}%"))
    for (file_orm,) in (await session.execute(file_state)).all():
        file_model = FileModel.model_validate_orm(file_orm)
        dst_path = dst.joinpath(file_model.filename.relative_to(src))
        file_model.filename = dst_path
        file_model.id = uuid.uuid4()
        file_model.updated_at = datetime.now()
        session.add(FileORM.from_model(file_model))
    await session.commit()

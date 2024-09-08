import uuid
from typing import Optional

from aiofiles.ospath import wrap
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)
from sqlalchemy.sql import select

from src.depends.sql import SQLDepends
from src.models.metadata import MetadataModel, MetadataORM
from src.models.slow_task import SlowTaskModel, SlowTaskORM
from src.service.classification import ClassificationModel, DeepDanbooruModel
from src.sql.file_crad import FileCRAD
from src.util.ffmpeg import FFmpegVideo
from src.util.file import FileResolver


async def slow_task():
    async with AsyncSession(SQLDepends.state) as session:
        task_state = (
            select(SlowTaskORM, MetadataORM)
            .join(MetadataORM, MetadataORM.id == SlowTaskORM.metadata_id)
            .where(SlowTaskORM.type == "video_convert")
        )

        while res_orm := (await session.execute(task_state)).first():
            (task_orm, metadata_orm) = res_orm.tuple()
            slow_task = SlowTaskModel.model_validate_orm(task_orm)
            metadata = MetadataModel.model_validate_orm(metadata_orm)
            filename = await FileResolver.get_metadata_from_uuid(slow_task.metadata_id)

            ffmpeg = FFmpegVideo(
                input_file=filename.joinpath("bin"),
                ffprobe=metadata.data["ffprobe"],
            )

            task = (
                ["video_low", 640, 1000],
                ["video_mid", 1280, 2000],
                ["video_high", 1920, 4000],
            )

            for prefix, x, y in task:
                if not ffmpeg.check(y, x):
                    res_path = await ffmpeg.down_scale(
                        filename.joinpath("bin"),
                        prefix=prefix,
                        width=y,
                        bitrate=x // 4,
                    )
                    _ = await FileCRAD(session).put(res_path, uuid.uuid4())

            res_path = await ffmpeg.thumbnail(
                filename.joinpath("bin"),
                prefix="thumbnail",
            )
            _ = await FileCRAD(session).put(res_path, uuid.uuid4())

            await session.delete(task_orm)
            await session.commit()

        task_state = (
            select(SlowTaskORM, MetadataORM)
            .join(MetadataORM, MetadataORM.id == SlowTaskORM.metadata_id)
            .where(
                or_(
                    SlowTaskORM.type == "classification",
                    SlowTaskORM.type == "classification_video",
                )
            )
        )
        model: Optional[ClassificationModel] = None

        while task_orm := (await session.execute(task_state)).scalar():
            if model is None:
                model = await wrap(DeepDanbooruModel.load)(
                    "https://github.com/AUTOMATIC1111/TorchDeepDanbooru/releases/download/v1/model-resnet_custom_v3.pt"
                )

            slow_task = SlowTaskModel.model_validate_orm(task_orm)

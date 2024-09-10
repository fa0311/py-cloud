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
from src.models.tag import TagModel, TagORM
from src.service.classification import (
    ClassificationModel,
    DeepDanbooruClassificationModel,
    ImageClassificationModel,
)
from src.sql.file_crad import FileCRAD
from src.util.ffmpeg import FFmpegVideo
from src.util.file import FileResolver


def all_classification(metadata_id: uuid.UUID, suffix: str = ""):
    types = [
        f"deepdanbooru_classification{suffix}",
        f"general_classification{suffix}",
        f"food_classification{suffix}",
    ]
    models = [SlowTaskModel(type=x, metadata_id=metadata_id) for x in types]
    return [SlowTaskORM.from_model(x) for x in models]


async def slow_task():
    async with AsyncSession(SQLDepends.state) as session:
        await video_convert(session)
        await classification(
            session,
            DeepDanbooruClassificationModel,
            "https://github.com/AUTOMATIC1111/TorchDeepDanbooru/releases/download/v1/model-resnet_custom_v3.pt",
            "deepdanbooru_classification",
            "deepdanbooru_classification_thumbnail",
        )
        await classification(
            session,
            ImageClassificationModel,
            "google/vit-base-patch16-224",
            "general_classification",
            "general_classification_thumbnail",
        )
        return await classification(
            session,
            ImageClassificationModel,
            "nateraw/food",
            "food_classification",
            "food_classification_thumbnail",
        )


async def video_convert(session: AsyncSession):
    task_state = (
        select(SlowTaskORM, MetadataORM)
        .join(MetadataORM, MetadataORM.id == SlowTaskORM.metadata_id)
        .where(SlowTaskORM.type == "video_convert")
    )

    while res_orm := (await session.execute(task_state)).first():
        (task_orm, metadata_orm) = res_orm.tuple()
        metadata = MetadataModel.model_validate_orm(metadata_orm)
        filename = FileResolver.get_metadata_from_uuid(metadata.id)

        ffmpeg = FFmpegVideo(
            input_file=filename.joinpath(f"bin{metadata.suffix}"),
            ffprobe=metadata.data["ffprobe"],
        )

        task = (
            ["video_low.mp4", 640, 1000],
            ["video_mid.mp4", 1280, 2000],
            ["video_high.mp4", 1920, 4000],
        )

        for suffix, x, y in task:
            if not ffmpeg.check(y, x):
                res_path = await ffmpeg.down_scale(
                    filename,
                    suffix=suffix,
                    width=y,
                    bitrate=x // 4,
                )
                _ = await FileCRAD(session).put(res_path)

        res_path = await ffmpeg.thumbnail(
            filename,
            prefix="normal",
        )
        _ = await FileCRAD(session).put(res_path)

        session.add_all(all_classification(metadata.id, "_thumbnail"))
        await session.delete(task_orm)
        await session.commit()


async def classification(
    session: AsyncSession,
    cls: type[ClassificationModel],
    model_name: str,
    type_1: str,
    type_2: str,
):
    task_state = (
        select(SlowTaskORM, MetadataORM)
        .join(MetadataORM, MetadataORM.id == SlowTaskORM.metadata_id)
        .where(or_(SlowTaskORM.type == type_1, SlowTaskORM.type == type_2))
    )
    model: Optional[ClassificationModel] = None

    while task_orm := (await session.execute(task_state)).first():
        if model is None:
            model = await wrap(cls.load)(model_name)

        (task_orm, metadata_orm) = task_orm.tuple()
        slow_task = SlowTaskModel.model_validate_orm(task_orm)
        metadata = MetadataModel.model_validate_orm(metadata_orm)
        filename = FileResolver.get_metadata_from_uuid(metadata.id)
        bin = filename.joinpath(f"bin{metadata.suffix}")
        if slow_task.type == type_1:
            tags = await wrap(model.classify)(bin)
        elif slow_task.type == type_2:
            tags = await wrap(model.classify)(filename.joinpath("thumbnail_normal.png"))
        else:
            raise ValueError("Invalid type")

        tag_models = [
            TagModel(
                metadata_id=metadata.id,
                tag_id=tag,
                tag_type=type_1,
            )
            for tag in tags
        ]

        session.add_all(TagORM.from_model(x) for x in tag_models)
        await session.delete(task_orm)
    await session.commit()
    del model

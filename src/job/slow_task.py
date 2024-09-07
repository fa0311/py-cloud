import shutil

from sqlalchemy.ext.asyncio import (
    AsyncSession,
)
from sqlalchemy.sql import select

from src.depends.sql import SQLDepends
from src.models.file import FileModel, FileORM
from src.models.slow_task import SlowTaskModel, SlowTaskORM
from src.service.metadata import put_hook
from src.util.ffmpeg import FFmpegVideo
from src.util.file import FileResolver


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

                task = (
                    ["video_low", 640, 1000],
                    ["video_mid", 1280, 2000],
                    ["video_high", 1920, 4000],
                )

                for prefix, x, y in task:
                    if not ffmpeg.check(y, x):
                        res_path = await ffmpeg.down_scale(
                            temp_dir,
                            prefix=prefix,
                            width=y,
                            bitrate=x // 4,
                        )
                        await put_hook(session, res_path, slow_task=False)

                res_path = await ffmpeg.thumbnail(
                    temp_dir,
                    prefix="thumbnail",
                )
                await put_hook(session, res_path, slow_task=False)

                for (other_orm,) in task_res[1:]:
                    other_file = FileModel.model_validate_orm(other_orm)
                    other_temp = await FileResolver.get_temp_from_data(
                        other_file.filename
                    )
                    await shutil.copy(temp_dir, other_temp)
                    await session.delete(other_orm)

            await session.delete(task_orm)
            await session.commit()

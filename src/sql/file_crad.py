import uuid
from datetime import datetime
from pathlib import Path

import aiofiles.os as os
from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)
from sqlalchemy.sql import select

from src.models.file import FileModel, FileORM
from src.models.metadata import MetadataModel, MetadataORM
from src.service.metadata import MetadataFile
from src.sql.sql import escape_path, sep


class FileCRAD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_empty(self, directory: Path):
        file_state = (
            select(FileORM, MetadataORM)
            .join(MetadataORM, MetadataORM.id == FileORM.metadata_id)
            .where(
                and_(
                    MetadataORM.directory == False,  # noqa
                    or_(
                        FileORM.filename == str(directory),
                        FileORM.filename.like(f"{escape_path(directory)}{sep}%"),
                    ),
                )
            )
        )

        return (await self.session.execute(file_state)).scalar() is None

    # async def is_empty(self, directory: Path):
    #     equal = FileORM.filename == str(directory)
    #     like = FileORM.filename.like(f"{escape_path(directory)}{sep}%")
    #     file_state = select(FileORM).where(or_(equal, like))
    #     return (await self.session.execute(file_state)).scalar() is None

    async def put(self, file: Path, id: uuid.UUID):
        metadata = await MetadataFile.factory(file)
        size = await os.stat(file)

        metadata_model = MetadataModel(
            id=id,
            directory=False,
            size=size.st_size,
            data=metadata.to_dict(),
            video=metadata.ffmpeg.is_video(),
            internet_media_type=metadata.get_internet_media_type(),
            created_at=datetime.now(),
        )

        file_model = FileModel(
            metadata_id=metadata_model.id,
            filename=file,
        )

        self.session.add(FileORM.from_model(file_model))
        self.session.add(MetadataORM.from_model(metadata_model))
        return metadata_model

    async def delete(self, file: Path):
        equal = FileORM.filename == str(file)
        like = FileORM.filename.like(f"{escape_path(file)}{sep}%")
        file_state = select(FileORM).where(or_(equal, like))
        for (file_orm,) in (await self.session.execute(file_state)).all():
            await self.session.delete(file_orm)

    async def move(self, src: Path, dst: Path):
        equal = FileORM.filename == str(src)
        like = FileORM.filename.like(f"{escape_path(src)}{sep}%")
        file_state = select(FileORM).where(or_(equal, like))
        for (file_orm,) in (await self.session.execute(file_state)).all():
            assert isinstance(file_orm, FileORM)
            file_model = FileModel.model_validate_orm(file_orm)
            dst_path = dst.joinpath(file_model.filename.relative_to(src))
            file_orm.created_at = datetime.now()
            file_orm.filename = str(dst_path)

    async def copy(self, src: Path, dst: Path):
        equal = FileORM.filename == str(src)
        like = FileORM.filename.like(f"{escape_path(src)}{sep}%")
        file_state = select(FileORM).where(or_(equal, like))
        for (file_orm,) in (await self.session.execute(file_state)).all():
            file_model = FileModel.model_validate_orm(file_orm)
            dst_path = dst.joinpath(file_model.filename.relative_to(src))
            file_model.filename = dst_path
            file_model.id = uuid.uuid4()
            file_model.created_at = datetime.now()
            self.session.add(FileORM.from_model(file_model))

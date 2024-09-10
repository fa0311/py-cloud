import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles.os as os
from sqlalchemy import and_, func, or_
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)
from sqlalchemy.sql import delete, select

from src.models.file import FileModel, FileORM
from src.models.metadata import MetadataModel, MetadataORM
from src.models.response import DirectoryResponseModel, FileResponseModel
from src.service.metadata import MetadataFile
from src.sql.sql import escape_path, sep


class FileCRAD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def isempty(self, directory: Path):
        file_state = select(FileORM).where(
            and_(
                FileORM.directory == False,  # noqa
                or_(
                    FileORM.filename == str(directory),
                    FileORM.filename.like(f"{escape_path(directory)}{sep}%"),
                ),
            )
        )
        return (await self.session.execute(file_state)).scalar() is None

    async def exists(self, file: Path):
        file_state = select(FileORM).where(FileORM.filename == str(file))
        return (await self.session.execute(file_state)).scalar() is not None

    async def isfile(self, file: Path):
        file_state = select(FileORM).where(
            and_(
                FileORM.filename == str(file),
                FileORM.directory == False,  # noqa
            )
        )
        return (await self.session.execute(file_state)).scalar() is not None

    async def isdir(self, directory: Path):
        file_state = select(FileORM).where(
            and_(
                FileORM.filename == str(directory),
                FileORM.directory == True,  # noqa
            )
        )
        return (await self.session.execute(file_state)).scalar() is not None

    async def getdir(self, file: Path):
        file_state = select(FileORM).where(
            and_(
                FileORM.filename == str(file),
                FileORM.directory == True,  # noqa
            )
        )
        data = (await self.session.execute(file_state)).one()

        file_state = (
            select(func.max(FileORM.created_at), func.sum(MetadataORM.size))
            .join(MetadataORM, MetadataORM.id == FileORM.metadata_id)
            .where(FileORM.filename.like(f"{escape_path(file)}%"))
        )
        metadata = (await self.session.execute(file_state)).one()

        return DirectoryResponseModel(
            last_update=metadata[0],
            size=metadata[1],
            file=FileModel.model_validate_orm(data.tuple()[0]),
        )

    async def getfile(self, file: Path):
        file_state = (
            select(FileORM, MetadataORM)
            .join(MetadataORM, MetadataORM.id == FileORM.metadata_id)
            .where(FileORM.filename == str(file))
        )
        data = (await self.session.execute(file_state)).one()
        return FileResponseModel(
            file=FileModel.model_validate_orm(data[0]),
            metadata=MetadataModel.model_validate_orm(data[1]),
        )

    async def listdir(self, directory: Path):
        file_state = select(FileORM).where(FileORM.pearent == str(directory))
        data = (await self.session.execute(file_state)).all()
        return [FileModel.model_validate_orm(file_orm) for (file_orm,) in data]

    async def put(self, file: Path, id: Optional[uuid.UUID] = None):
        metadata = await MetadataFile.factory(file)
        size = await os.stat(file)

        metadata_model = MetadataModel(
            id=id or uuid.uuid4(),
            suffix=file.suffix,
            size=size.st_size,
            data=metadata.to_dict(),
            video=metadata.is_video(),
            image=metadata.is_image(),
            internet_media_type=metadata.get_internet_media_type(),
            created_at=datetime.now(),
        )

        file_model = FileModel(
            metadata_id=metadata_model.id,
            filename=file,
            pearent=file.parent,
            directory=False,
        )

        self.session.add(FileORM.from_model(file_model))
        self.session.add(MetadataORM.from_model(metadata_model))
        return metadata_model

    async def mkdir(self, directory: Path, id: Optional[uuid.UUID] = None):
        metadata_model = MetadataModel(
            id=id or uuid.uuid4(),
            suffix="",
            size=0,
            data={},
            video=False,
            image=False,
            internet_media_type="application/octet-stream",
            created_at=datetime.now(),
        )

        file_model = FileModel(
            metadata_id=metadata_model.id,
            filename=directory,
            pearent=directory.parent,
            directory=True,
        )

        self.session.add(FileORM.from_model(file_model))
        self.session.add(MetadataORM.from_model(metadata_model))
        return metadata_model

    async def delete(self, file: Path):
        file_state = delete(FileORM).where(
            or_(
                FileORM.filename == str(file),
                FileORM.filename.like(f"{escape_path(file)}{sep}%"),
            )
        )
        await self.session.execute(file_state)

    async def empty(self, directory: Path):
        file_state = delete(FileORM).where(
            FileORM.filename.like(f"{escape_path(directory)}{sep}%"),
        )
        await self.session.execute(file_state)

    async def move(self, src: Path, dst: Path):
        file_state = select(FileORM).where(
            or_(
                FileORM.filename == str(src),
                FileORM.filename.like(f"{escape_path(src)}{sep}%"),
            )
        )
        for all in (await self.session.execute(file_state)).all():
            (file_orm,) = all.tuple()
            file_model = FileModel.model_validate_orm(file_orm)
            dst_path = dst.joinpath(file_model.filename.relative_to(src))
            file_orm.created_at = datetime.now()
            file_orm.filename = str(dst_path)
            file_orm.pearent = str(dst_path.parent)

    async def copy(self, src: Path, dst: Path):
        file_state = select(FileORM).where(
            or_(
                FileORM.filename == str(src),
                FileORM.filename.like(f"{escape_path(src)}{sep}%"),
            )
        )
        for all in (await self.session.execute(file_state)).all():
            (file_orm,) = all.tuple()
            file_model = FileModel.model_validate_orm(file_orm)
            dst_path = dst.joinpath(file_model.filename.relative_to(src))
            file_model.filename = dst_path
            file_model.pearent = dst_path.parent
            file_model.id = uuid.uuid4()
            file_model.created_at = datetime.now()
            self.session.add(FileORM.from_model(file_model))

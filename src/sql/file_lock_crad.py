from pathlib import Path

from aiofiles import os
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
)
from sqlalchemy.sql import select

from src.models.file_lock import FileLockModel, FileLockORM
from src.sql.sql import escape_path, sep
from src.util import aioshutils as shutil


class FileLockCRADError(Exception):
    pass


class FileLockTransaction:
    def __init__(self, engine: AsyncEngine, file: Path):
        self.file = file
        self.session = AsyncSession(engine)

    async def __aenter__(self):
        self.file_lock = FileLockCRAD(self.session, self.file)
        if await self.file_lock.is_lock():
            raise FileLockCRADError(f"{self.file} is locked")
        else:
            await self.file_lock.lock()
            await self.session.commit()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            await self.file_lock.unlock()
            await self.session.commit()
        finally:
            await self.session.close()


class FileGuard:
    def __init__(self, *file: Path):
        self.file = file

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            for f in self.file:
                if await os.path.isfile(f):
                    await os.remove(f)
                elif await os.path.isdir(f):
                    await shutil.rmtree(f)
            raise exc_val


class FileMoveGuard:
    def __init__(self, src: Path, dst: Path):
        self.src = src
        self.dst = dst

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await shutil.move(self.dst, self.src)


class FileLockCRAD:
    def __init__(self, session: AsyncSession, file: Path):
        self.session = session
        self.file = file

    async def is_lock(self):
        equal = FileLockORM.filename == str(self.file)
        like = FileLockORM.filename.like(f"{escape_path(self.file)}{sep}%")
        file_state = select(FileLockORM).where(or_(equal, like))
        return (await self.session.execute(file_state)).scalar() is not None

    async def lock(self):
        lock_model = FileLockModel(filename=self.file)
        self.session.add(FileLockORM.from_model(lock_model))

    async def unlock(self):
        equal = FileLockORM.filename == str(self.file)
        file_state = select(FileLockORM).where(equal)
        (file_rock_orm,) = (await self.session.execute(file_state)).one()
        await self.session.delete(file_rock_orm)

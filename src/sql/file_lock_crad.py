from pathlib import Path

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
)
from sqlalchemy.sql import select

from src.models.file import FileLockModel, FileLockORM
from src.sql.sql import escape_path, sep


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

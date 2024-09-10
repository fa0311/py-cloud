import aiofiles.os as os
from sqlalchemy.exc import DatabaseError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from src.models.environ import Environ
from src.sql.file_crad import FileCRAD
from src.sql.sql import SQLBase
from src.util.file import FileResolver


class SQLDepends:
    state: AsyncEngine

    @staticmethod
    async def init(conn: AsyncSession):
        dir_list = [
            FileResolver.base_path.joinpath("..").parent,
            FileResolver.metadata_path.joinpath("..").parent,
            FileResolver.trashbin_path.joinpath("..").parent,
        ]
        for dir in dir_list:
            await os.makedirs(dir, exist_ok=True)
            if not await FileCRAD(conn).exists(dir):
                await FileCRAD(conn).mkdir(dir)

    @staticmethod
    @retry(retry=retry_if_exception_type(DatabaseError), stop=stop_after_attempt(3))
    async def start():
        env = Environ()
        SQLDepends.state = create_async_engine(env.DB_URL, echo=env.SQL_ECHO)
        async with SQLDepends.state.begin() as conn:
            await conn.run_sync(SQLBase.metadata.create_all)
        async with AsyncSession(SQLDepends.state) as session:
            await SQLDepends.init(session)
            await session.commit()

    @staticmethod
    async def test(drop_all: bool = False):
        env = Environ()
        name = f"{env.DB_URL}_test"
        SQLDepends.state = create_async_engine(name, echo=env.SQL_ECHO)
        async with SQLDepends.state.begin() as conn:
            if drop_all:
                await conn.run_sync(SQLBase.metadata.drop_all)
            await conn.run_sync(SQLBase.metadata.create_all)
        async with AsyncSession(SQLDepends.state) as session:
            await SQLDepends.init(session)
            await session.commit()

    @staticmethod
    async def stop():
        await SQLDepends.state.dispose()

    @staticmethod
    async def depends():
        async with AsyncSession(SQLDepends.state) as session:
            yield session

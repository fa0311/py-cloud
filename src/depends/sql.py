from sqlalchemy.exc import DatabaseError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
)
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from src.models.environ import Environ


class SQLBase(DeclarativeBase):
    pass


class SQLDepends:
    state: AsyncEngine

    @staticmethod
    @retry(retry=retry_if_exception_type(DatabaseError), stop=stop_after_attempt(3))
    async def start():
        env = Environ()
        SQLDepends.state = create_async_engine(env.DB_URL, echo=env.SQL_ECHO)
        async with SQLDepends.state.begin() as conn:
            await conn.run_sync(SQLBase.metadata.create_all)

    @staticmethod
    async def test(drop_all: bool = False):
        env = Environ()
        name = f"{env.DB_URL}_test"
        SQLDepends.state = create_async_engine(name, echo=env.SQL_ECHO)
        async with SQLDepends.state.begin() as conn:
            if drop_all:
                await conn.run_sync(SQLBase.metadata.drop_all)
            await conn.run_sync(SQLBase.metadata.create_all)

    @staticmethod
    async def stop():
        await SQLDepends.state.dispose()

    @staticmethod
    async def depends():
        async with AsyncSession(SQLDepends.state) as session:
            yield session

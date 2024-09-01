from retry import retry
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
)

from src.models.environ import Environ


class SQLBase(DeclarativeBase):
    pass


class SQLDepends:
    state: Engine

    @staticmethod
    @retry(DatabaseError, tries=3, delay=2)
    def start():
        env = Environ()
        SQLDepends.state = create_engine(env.DB_URL, echo=env.SQL_ECHO)
        SQLBase.metadata.create_all(bind=SQLDepends.state)

    @staticmethod
    def stop():
        SQLDepends.state.dispose()

    @staticmethod
    def depends():
        with Session(SQLDepends.state) as session:
            yield session

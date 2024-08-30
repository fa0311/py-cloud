from retry import retry
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError
from sqlmodel import Session, SQLModel, create_engine

from src.models.environ import Environ


class SQLDepends:
    state: Engine

    @staticmethod
    @retry(DatabaseError, tries=3, delay=2)
    def start():
        env = Environ()
        SQLDepends.state = create_engine(env.DB_URL, echo=env.SQL_ECHO)
        SQLModel.metadata.create_all(SQLDepends.state)

    @staticmethod
    def stop():
        SQLDepends.state.dispose()

    @staticmethod
    def depends():
        with Session(SQLDepends.state) as session:
            yield session

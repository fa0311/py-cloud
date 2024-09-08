import uuid

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import CHAR, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)
from sqlalchemy.sql import select


class SQLBase(DeclarativeBase):
    pass


class OrmMixin:
    @classmethod
    def from_model(cls, value: BaseModel):
        data = value.model_dump(mode="json", exclude_none=True)
        return cls(**data)


class ModelBase(BaseModel):
    @classmethod
    def model_validate_orm(cls, orm):
        data = orm.__dict__
        return cls.model_validate(data, strict=False)


class UserOrm(SQLBase, OrmMixin):
    __tablename__ = "user"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)


class UserModel(ModelBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)


class TagOrm(SQLBase, OrmMixin):
    __tablename__ = "tag"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    tag: Mapped[str] = mapped_column(CHAR(255), nullable=False)


class TagModel(ModelBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID = Field()
    tag: str = Field()


class Environ(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    DB_URL: str = Field(
        default="sqlite:///sample.db",
    )


if __name__ == "__main__":
    env = Environ()

    engine = create_engine(env.DB_URL)
    SQLBase.metadata.create_all(engine)

    with engine.connect() as session:
        state = (
            select(UserOrm, TagOrm)
            .join(TagOrm, UserOrm.id == TagOrm.user_id)
            .where(UserOrm.id == "aaaaa")
        )
        for res in session.execute(state).all():
            (user_orm, tag_orm) = res.tuple()

            _ = user_orm

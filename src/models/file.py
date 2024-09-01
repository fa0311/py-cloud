import pathlib
import uuid
from datetime import datetime

from pydantic import Field
from sqlalchemy import CHAR, JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from src.depends.sql import SQLBase
from src.sql.sql import ModelBase, ORMMixin


class FileORM(SQLBase, ORMMixin):
    __tablename__ = "file"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    directory: Mapped[bool] = mapped_column(Boolean, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    data: Mapped[str] = mapped_column(JSON, nullable=False)
    last_time: Mapped[int] = mapped_column(DateTime, nullable=False)


class FileModel(ModelBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    directory: bool = Field()
    size: int = Field()
    filename: pathlib.Path = Field()
    data: dict = Field(default_factory=dict)
    last_time: datetime = Field(default_factory=datetime.now)

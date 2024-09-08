import uuid
from datetime import datetime
from pathlib import Path

from pydantic import Field
from sqlalchemy import CHAR, DateTime, String
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from src.depends.sql import SQLBase
from src.sql.sql import ModelBase, ORMMixin


class FileORM(SQLBase, ORMMixin):
    __tablename__ = "file"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    metadata_id: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    # directory: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # size: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # data: Mapped[str] = mapped_column(JSON, nullable=False)
    # video: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # internet_media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class FileModel(ModelBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    metadata_id: uuid.UUID = Field()
    # directory: bool = Field()
    # size: int = Field()
    filename: Path = Field()
    # data: dict = Field(default_factory=dict)
    # video: bool = Field()
    # internet_media_type: str = Field(default="application/octet-stream")
    created_at: datetime = Field(default_factory=datetime.now)
    # updated_at: datetime = Field(default_factory=datetime.now)


class FileLockORM(SQLBase, ORMMixin):
    __tablename__ = "file_lock"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)


class FileLockModel(ModelBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    filename: Path = Field()

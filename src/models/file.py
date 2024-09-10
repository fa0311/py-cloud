import uuid
from datetime import datetime
from pathlib import Path

from pydantic import Field
from sqlalchemy import CHAR, Boolean, DateTime, String
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from src.sql.sql import ModelBase, ORMMixin, SQLBase


class FileORM(SQLBase, ORMMixin):
    __tablename__ = "file"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    metadata_id: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    directory: Mapped[bool] = mapped_column(Boolean, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class FileModel(ModelBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    metadata_id: uuid.UUID = Field()
    directory: bool = Field()
    filename: Path = Field()
    created_at: datetime = Field(default_factory=datetime.now)

import uuid
from pathlib import Path

from pydantic import Field
from sqlalchemy import CHAR, String
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from src.sql.sql import ModelBase, ORMMixin, SQLBase


class FileLockORM(SQLBase, ORMMixin):
    __tablename__ = "file_lock"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)


class FileLockModel(ModelBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    filename: Path = Field()

import uuid
from datetime import datetime

from pydantic import Field
from sqlalchemy import CHAR, DateTime, Integer
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from src.depends.sql import SQLBase
from src.sql.sql import ModelBase, ORMMixin


class TagORM(SQLBase, ORMMixin):
    __tablename__ = "tag"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    metadata_id: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    tag_id: Mapped[int] = mapped_column(Integer, nullable=False)
    tag_type: Mapped[str] = mapped_column(CHAR(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class TagModel(ModelBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    metadata_id: uuid.UUID = Field()
    tag_id: int = Field()
    tag_type: str = Field()
    created_at: datetime = Field(default_factory=datetime.now)

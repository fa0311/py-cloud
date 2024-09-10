import uuid
from datetime import datetime

from pydantic import Field
from sqlalchemy import CHAR, JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from src.sql.sql import ModelBase, ORMMixin, SQLBase


class MetadataORM(SQLBase, ORMMixin):
    __tablename__ = "metadata"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    suffix: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[str] = mapped_column(JSON, nullable=False)
    video: Mapped[bool] = mapped_column(Boolean, nullable=False)
    image: Mapped[bool] = mapped_column(Boolean, nullable=False)
    internet_media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class MetadataModel(ModelBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    suffix: str = Field()
    size: int = Field()
    data: dict = Field(default_factory=dict)
    video: bool = Field()
    image: bool = Field()
    internet_media_type: str = Field(default="application/octet-stream")
    created_at: datetime = Field(default_factory=datetime.now)

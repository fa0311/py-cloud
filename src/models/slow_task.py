import uuid
from datetime import datetime

from pydantic import Field
from sqlalchemy import CHAR, DateTime
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from src.sql.sql import ModelBase, ORMMixin, SQLBase


class SlowTaskORM(SQLBase, ORMMixin):
    __tablename__ = "slow_task"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    type: Mapped[str] = mapped_column(CHAR(255), nullable=False)
    metadata_id: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    add_time: Mapped[int] = mapped_column(DateTime, nullable=False)


class SlowTaskModel(ModelBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    type: str = Field()
    metadata_id: uuid.UUID = Field()
    add_time: datetime = Field(default_factory=datetime.now)

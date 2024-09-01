import uuid
from datetime import datetime

from pydantic import Field
from sqlalchemy import CHAR, DateTime, String
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from src.depends.sql import SQLBase
from src.sql.sql import ModelBase, ORMMixin


class SlowTaskORM(SQLBase, ORMMixin):
    __tablename__ = "slow_task"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_id: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    last_time: Mapped[int] = mapped_column(DateTime, nullable=False)


class SlowTaskModel(ModelBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field()
    file_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    last_time: datetime = Field(default_factory=datetime.now)

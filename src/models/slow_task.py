import pathlib
import uuid
from dataclasses import field

from sqlalchemy import CHAR, TEXT, VARCHAR
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from src.depends.sql import SQLBase
from src.sql.sql import ModelBase, ORMMixin


class SlowTaskORM(SQLBase, ORMMixin):
    __tablename__ = "slow_task"
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    filename: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    data: Mapped[str] = mapped_column(TEXT, nullable=False)


class SlowTaskModel(ModelBase):
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    filename: pathlib.Path = field()
    data: dict = field(default_factory=dict)

from os import sep as _sep
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import (
    DeclarativeBase,
)


def escape_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


sep = _sep.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SQLBase(DeclarativeBase):
    pass


class ORMMixin:
    @classmethod
    def from_model(cls, value: BaseModel):
        data = value.model_dump(
            mode="json",
            exclude_none=True,
        )
        return cls(**data)


class ModelBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def model_validate_orm(cls, orm):
        data = orm.__dict__
        return cls.model_validate(data, strict=False)

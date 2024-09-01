import json

from pydantic import BaseModel, ConfigDict


class ORMMixin:
    @classmethod
    def from_model(cls, value: BaseModel):
        data = value.model_dump(
            mode="json",
            exclude_none=True,
        )

        args = {k: json.dumps(v) if isinstance(v, dict) else v for k, v in data.items()}
        return cls(**args)


class ModelBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def model_validate_orm(cls, orm):
        data = orm[0].__dict__
        args = {
            k: json.loads(data[k]) if v.annotation is dict else data[k]
            for k, v in cls.model_fields.items()
        }
        return cls.model_validate(args, strict=False)

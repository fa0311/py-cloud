from pydantic import BaseModel, ConfigDict


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

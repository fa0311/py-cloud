from datetime import datetime

from pydantic import Field

from src.models.file import FileModel
from src.models.metadata import MetadataModel
from src.sql.sql import ModelBase


class DirectoryResponseModel(ModelBase):
    last_update: datetime = Field()
    size: int = Field()
    file: FileModel = Field()


class FileResponseModel(ModelBase):
    file: FileModel = Field()
    metadata: MetadataModel = Field()

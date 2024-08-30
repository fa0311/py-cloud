from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings


class LogLevel(str, Enum):
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    WARN = "WARN"
    INFO = "INFO"
    DEBUG = "DEBUG"
    NOTSET = "NOTSET"


class Environ(BaseSettings):
    def __init__(self):
        super().__init__()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    DB_URL: str = Field(
        default="sqlite:///py_cloud.db",
        description="データベースのURL, 例: mysql+mysqlconnector://root:@localhost:3306/py_cloud",
    )
    ROOT_PATH: str = Field(
        default="/",
        description="ルートパス, 例: /api",
    )

    LOG_LEVEL: LogLevel = Field(
        default=LogLevel.WARNING,
        description="ログレベル",
    )
    SQL_ECHO: bool = Field(
        default=False,
        description="SQLのログを出力するか",
    )

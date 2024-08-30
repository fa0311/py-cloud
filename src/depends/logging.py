import logging
import os
from logging import Logger, handlers
from pathlib import Path

from coloredlogs import ColoredFormatter

from src.models.environ import Environ


class LoggingDepends:
    state: Logger

    @staticmethod
    def init(path: Path):
        env = Environ()
        fmt = "[%(levelname)s] %(asctime)s [%(name)s][%(filename)s:%(lineno)d] %(message)s"
        level = env.LOG_LEVEL.value

        os.makedirs(path.parent, exist_ok=True)
        file_handler = handlers.TimedRotatingFileHandler(
            filename=path,
            when="D",
            interval=1,
            backupCount=90,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(fmt))

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(ColoredFormatter(fmt))

        logging.basicConfig(level=level, handlers=[file_handler, stream_handler])

        LoggingDepends.state = logging.getLogger("main")

    @staticmethod
    def depends():
        yield LoggingDepends.state

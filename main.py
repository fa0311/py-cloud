from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.app.upload import router as upload
from src.app.webdav import router as webdav
from src.depends.job import Job
from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends
from src.models.environ import Environ
from src.util.file import FileResolver


@asynccontextmanager
async def lifespan(app: FastAPI):
    await LoggingDepends.init(path=Path("logs/main.log"))
    await SQLDepends.start()
    await Job.start()
    yield
    await Job.stop()
    await SQLDepends.stop()


@asynccontextmanager
async def test_lifespan(app: FastAPI):
    FileResolver.set_temp()
    await LoggingDepends.init(path=Path("logs/testing.log"))
    await SQLDepends.test(drop_all=True)
    await Job.start()
    yield
    await Job.stop()
    await SQLDepends.stop()


def init_fastapi(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(webdav)
    app.include_router(upload)


env = Environ()
life = lifespan if not env.TESTING else test_lifespan
app = FastAPI(lifespan=life, root_path=env.ROOT_PATH)
init_fastapi(app)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=env.HOST,
        port=env.PORT,
        # log_config={
        #     "version": 1,
        #     "disable_existing_loggers": False,
        # },
        reload=(not env.TESTING),
    )

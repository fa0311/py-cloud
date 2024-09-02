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


@asynccontextmanager
async def lifespan(app: FastAPI):
    LoggingDepends.init(path=Path("logs/main.log"))
    SQLDepends.start()
    Job.start()
    yield
    Job.stop()
    SQLDepends.stop()


env = Environ()
app = FastAPI(lifespan=lifespan, root_path=env.ROOT_PATH)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload)
app.include_router(webdav)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        # log_config={
        #     "version": 1,
        #     "disable_existing_loggers": False,
        # },
        reload=True,
    )

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.background import BackgroundScheduler

from src.job.slow_task import slow_task
from src.models.environ import Environ


class Job:
    state: BackgroundScheduler

    @staticmethod
    async def start():
        env = Environ()
        Job.state = AsyncIOScheduler()
        Job.state.add_job(slow_task, "interval", seconds=10)

        if env.JOB_ENABLE:
            Job.state.start()

    @staticmethod
    async def stop():
        await Job.state.shutdown()

    @staticmethod
    async def depends():
        yield Job.state

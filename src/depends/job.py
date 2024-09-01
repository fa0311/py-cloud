from apscheduler.schedulers.background import BackgroundScheduler

from src.job.slow_task import slow_task
from src.models.environ import Environ


class Job:
    state: BackgroundScheduler

    @staticmethod
    def start():
        env = Environ()
        Job.state = BackgroundScheduler()
        Job.state.add_job(slow_task, "interval", seconds=10)

        if env.JOB_ENABLE:
            Job.state.start()

    @staticmethod
    def stop():
        Job.state.shutdown()

    @staticmethod
    def depends():
        yield Job.state

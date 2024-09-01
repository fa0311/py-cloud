from sqlalchemy.orm import Session
from sqlalchemy.sql import select

from src.depends.sql import SQLDepends
from src.models.file import FileModel, FileORM
from src.models.slow_task import SlowTaskModel, SlowTaskORM


def slow_task():
    with Session(SQLDepends.state) as session:
        task_state = select(SlowTaskORM)

        for tasl_orm in session.execute(task_state).all():
            slow_task = SlowTaskModel.model_validate_orm(tasl_orm)

            file_state = select(FileORM).where(FileORM.id == str(slow_task.file_id))
            file_orm = session.execute(file_state).one()
            file_model = FileModel.model_validate_orm(file_orm)

            print(file_model)

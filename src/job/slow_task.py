import pathlib

from sqlalchemy.orm import Session
from sqlalchemy.sql import select

from src.depends.sql import SQLDepends
from src.models.slow_task import SlowTaskModel, SlowTaskORM


def slow_task():
    with Session(SQLDepends.state) as session:
        model = SlowTaskModel(
            filename=pathlib.Path("example.txt"),
            data={"key": "value"},
        )
        session.add(SlowTaskORM.from_model(model))
        session.commit()

        statement = select(SlowTaskORM)

        for row in session.execute(statement).all():
            res = SlowTaskModel.model_validate_orm(row)
            print(res)

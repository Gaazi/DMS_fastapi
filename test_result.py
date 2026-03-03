from app.models import Institution
from sqlmodel import Session, select, create_engine
import os

engine = create_engine('sqlite://')
from sqlmodel import SQLModel
SQLModel.metadata.create_all(engine)

def test():
    with Session(engine) as session:
        stmt = select(Institution).distinct()
        res = session.exec(stmt)
        print(f"Result type: {type(res)}")
        try:
            print("Calling .all()...")
            print(res.all())
            print("Success!")
        except Exception as e:
            print(f"Failed .all(): {e}")
            print(f"Dir: {dir(res)}")

test()

from sqlmodel import SQLModel, Field, create_engine, Session, select
from typing import Optional
from sqlalchemy import Column, Integer

class TestTable(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer))

# Create DB with one row having 'institution_id'
engine = create_engine("sqlite://")
SQLModel.metadata.create_all(engine)

from sqlalchemy import text
with engine.connect() as conn:
    conn.execute(text("INSERT INTO testtable (institution_id) VALUES (42)"))
    conn.commit()

with Session(engine) as session:
    obj = session.exec(select(TestTable)).first()
    print(f"Loaded obj. inst_id: {obj.inst_id}")
    try:
        print(f"Data in __dict__: {obj.__dict__}")
    except:
        pass

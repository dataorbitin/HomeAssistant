from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


def insert_for(session, model):
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        return pg_insert(model)
    if dialect == "sqlite":
        return sqlite_insert(model)
    raise RuntimeError("Unsupported database dialect")

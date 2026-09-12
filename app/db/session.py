from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def normalize_url(value: str) -> str:
    if value.startswith("postgres://"):
        value = "postgresql://" + value.removeprefix("postgres://")
    url = make_url(value)
    if url.drivername in {"postgresql", "postgresql+psycopg2"}:
        url = url.set(drivername="postgresql+psycopg")
    return url.render_as_string(hide_password=False)


def create_engine(database_url: str):
    url = normalize_url(database_url)
    kwargs = {"pool_pre_ping": True, "hide_parameters": True}
    if url.startswith("postgresql"):
        kwargs["connect_args"] = {"prepare_threshold": None, "connect_timeout": 10}
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 5
    engine = create_async_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def sqlite_foreign_keys(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)

import json
import logging


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {"level": record.levelname, "logger": record.name, "event": record.getMessage()}
        )


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.getLogger().handlers = [handler]
    logging.getLogger().setLevel(logging.INFO)
    for name in ("httpx", "httpcore", "sqlalchemy.engine", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.WARNING)

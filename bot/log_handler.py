import logging
from datetime import datetime

from sqlalchemy.orm import sessionmaker

_INCLUDED_PREFIXES = ("bot.", "web.", "discord")


class DBLogHandler(logging.Handler):
    def __init__(self, engine):
        super().__init__()
        self._Session = sessionmaker(bind=engine)
        self._emitting = False

    def emit(self, record: logging.LogRecord) -> None:
        if self._emitting:
            return
        if not any(record.name.startswith(p) for p in _INCLUDED_PREFIXES):
            return
        self._emitting = True
        try:
            from bot.database import AppLog

            with self._Session() as session:
                entry = AppLog(
                    timestamp=datetime.utcfromtimestamp(record.created),
                    level=record.levelname,
                    logger=record.name,
                    message=record.getMessage(),
                )
                session.add(entry)
                session.commit()
        except Exception:
            self.handleError(record)
        finally:
            self._emitting = False


def setup_db_logging(engine) -> None:
    handler = DBLogHandler(engine)
    handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bot.db.models import AppLog


def get_logs(
    session: Session,
    level: str | None = None,
    logger_filter: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AppLog], int]:
    filters = []
    if level:
        filters.append(AppLog.level == level)
    if logger_filter:
        filters.append(AppLog.logger.ilike(f"%{logger_filter}%"))
    if search:
        filters.append(AppLog.message.ilike(f"%{search}%"))

    count_stmt = select(func.count()).select_from(AppLog)
    data_stmt = select(AppLog).order_by(AppLog.timestamp.desc())
    if filters:
        count_stmt = count_stmt.where(*filters)
        data_stmt = data_stmt.where(*filters)

    total = session.scalar(count_stmt) or 0
    rows = session.execute(data_stmt.offset(offset).limit(limit)).scalars().all()
    return rows, total

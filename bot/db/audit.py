import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bot.db.models import AuditLog


def record(
    session: Session,
    *,
    actor_email: str,
    actor_role: str,
    action: str,
    target_type: str,
    target_id: str,
    details: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        actor_email=actor_email,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details_json=json.dumps(details or {}, default=str),
    )
    session.add(entry)
    session.flush()
    return entry


def list_recent(session: Session, limit: int = 100) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    return list(session.scalars(stmt).all())


def search(
    session: Session,
    *,
    action_contains: str | None = None,
    actor_email_contains: str | None = None,
    limit: int = 100,
) -> list[AuditLog]:
    stmt = select(AuditLog)
    if action_contains:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action_contains}%"))
    if actor_email_contains:
        stmt = stmt.where(AuditLog.actor_email.ilike(f"%{actor_email_contains}%"))
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
    return list(session.scalars(stmt).all())


def search_paginated(
    session: Session,
    *,
    action_contains: str | None = None,
    actor_email_contains: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    stmt = select(AuditLog)
    if action_contains:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action_contains}%"))
    if actor_email_contains:
        stmt = stmt.where(AuditLog.actor_email.ilike(f"%{actor_email_contains}%"))
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= date_to + " 23:59:59")
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    return list(session.scalars(stmt).all()), total


def distinct_actions(session: Session) -> list[str]:
    rows = session.execute(select(AuditLog.action).distinct().order_by(AuditLog.action)).scalars().all()
    return list(rows)

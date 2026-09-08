import json

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_action(db: Session, user_id: int | None, action: str, entity_type: str,
               entity_id: int | None, details: dict | None = None) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=json.dumps(details or {}),
    )
    db.add(entry)
    return entry
from sqlalchemy.orm import Session

from app.models.entities import Interaction
from app.models.schemas import ActivityIn


def log_activity(db: Session, payload: ActivityIn, user_id: int) -> Interaction:
    row = Interaction(
        user_id=user_id,
        book_id=payload.book_id,
        event_type=payload.event_type,
        dwell_ms=payload.dwell_ms,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

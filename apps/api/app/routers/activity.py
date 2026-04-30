from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.entities import User
from app.models.schemas import ActivityIn, InteractionOut
from app.services.activity_service import log_activity

router = APIRouter(prefix="/user", tags=["activity"])


@router.post("/activity", response_model=InteractionOut)
def user_activity(
    payload: ActivityIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = log_activity(db, payload, user_id=current_user.id)
    return {"ok": True, "interaction_id": row.id}

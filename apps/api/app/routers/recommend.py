from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.entities import Interaction, User
from app.models.schemas import RecommendResponse
from app.services.recommendation_service import get_recommendation_service

router = APIRouter(tags=["recommendation"])


@router.get("/recommend", response_model=RecommendResponse)
def recommend(
    top_k: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    read_rows = (
        db.query(Interaction.book_id)
        .filter(Interaction.user_id == current_user.id, Interaction.event_type == "read")
        .all()
    )
    read_book_ids = [int(r.book_id) for r in read_rows]
    svc = get_recommendation_service()
    items = svc.recommend(user_id=current_user.id, top_k=top_k, read_book_ids=read_book_ids)
    return {"items": items}


@router.get("/recommendations", response_model=RecommendResponse)
def recommendations_alias(
    top_k: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return recommend(top_k=top_k, db=db, current_user=current_user)

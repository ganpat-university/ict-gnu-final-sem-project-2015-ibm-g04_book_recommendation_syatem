from fastapi import APIRouter, Query

from app.services.search_service import get_search_service

router = APIRouter(tags=["search"])


@router.get("/search")
def search_books(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=50)):
    svc = get_search_service()
    return {"items": svc.search(q=q, limit=limit)}


@router.get("/search/suggest")
def suggest_books(q: str = Query(..., min_length=1), limit: int = Query(8, ge=1, le=20)):
    svc = get_search_service()
    return {"items": svc.suggest(q=q, limit=limit)}

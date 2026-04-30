from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.schemas import BookListResponse, SimilarResponse
from app.services.recommendation_service import get_recommendation_service
from app.services.search_service import get_search_service

router = APIRouter(tags=["books"])


@router.get("/books", response_model=BookListResponse)
def list_books(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)):
    svc = get_search_service()
    if svc.books_df.empty:
        return {"items": [], "page": page, "limit": limit}
    start = (page - 1) * limit
    end = start + limit
    cols = ["book_id", "title", "author", "avg_rating"]
    cols = [c for c in cols if c in svc.books_df.columns]
    items = svc.books_df.iloc[start:end][cols].to_dict("records")
    return {"items": items, "page": page, "limit": limit}


@router.get("/books/{book_id}")
def book_detail(book_id: int):
    svc = get_search_service()
    if svc.books_df.empty:
        raise HTTPException(status_code=404, detail="Book not found")
    row = svc.books_df[svc.books_df["book_id"] == book_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="Book not found")
    record = row.iloc[0].to_dict()
    return {"item": record}


@router.get("/books/{book_id}/similar", response_model=SimilarResponse)
def similar_books(book_id: int, n: int = Query(6, ge=1, le=24)):
    rec = get_recommendation_service()
    # Use hybrid explainability path by simulating "because you read"
    items = []
    if rec.hybrid is not None:
        sims = rec.hybrid.content.get_similar_to_book(book_id=book_id, n=n)
        if sims is not None and not sims.empty:
            for _, row in sims.iterrows():
                items.append(
                    {
                        "book": {
                            "book_id": int(row.get("book_id", 0)),
                            "title": row.get("title"),
                            "author": row.get("author"),
                            "year": int(row.get("year")) if row.get("year") is not None and str(row.get("year")).isdigit() else None,
                            "avg_rating": float(row.get("avg_rating")) if row.get("avg_rating") is not None else None,
                            "rating_count": None,
                            "image_url_m": row.get("image_url_m"),
                        },
                        "score": float(row.get("similarity_score", 0.0)) * 100.0,
                        "reasons": [f"Because you read book #{book_id}"],
                        "badges": ["Strong Match"],
                    }
                )
    return {"items": items[:n]}

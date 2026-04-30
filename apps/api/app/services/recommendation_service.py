from functools import lru_cache

import pandas as pd

from data_loader import DataLoader, load_books_seed
from recommenders.hybrid import HybridRecommender


class RecommendationService:
    def __init__(self, books_df: pd.DataFrame | None = None, hybrid: HybridRecommender | None = None):
        self.books_df = books_df if books_df is not None else pd.DataFrame()
        self.hybrid = hybrid

    def recommend(self, user_id: int, top_k: int = 12, read_book_ids: list[int] | None = None):
        if self.hybrid is not None:
            return self.hybrid.get_recommendations_explained(
                user_id=user_id,
                n=top_k,
                read_book_ids=read_book_ids or [],
            )

        # Deterministic fallback from seed catalog if model stack unavailable
        seed = load_books_seed()
        if not seed:
            return []
        read_set = {int(x) for x in (read_book_ids or []) if str(x).isdigit()}
        ranked = sorted(seed, key=lambda b: (b.get("ratingsCount", 0), b.get("rating", 0)), reverse=True)
        out = []
        for b in ranked:
            if b.get("id") and isinstance(b["id"], str) and b["id"].startswith("b"):
                try:
                    bid = int(b["id"][1:])
                except Exception:
                    bid = None
            else:
                bid = b.get("book_id")
            if bid in read_set:
                continue
            out.append(
                {
                    "book": {
                        "book_id": int(bid or 0),
                        "title": b.get("title"),
                        "author": b.get("author"),
                        "year": b.get("year"),
                        "avg_rating": b.get("rating"),
                        "rating_count": b.get("ratingsCount"),
                        "image_url_m": None,
                    },
                    "score": float(b.get("rating", 0)) * 20,
                    "reasons": ["Popularity fallback recommendation"],
                    "badges": ["Reader Favorite"],
                }
            )
            if len(out) >= top_k:
                break
        return out


@lru_cache(maxsize=1)
def get_recommendation_service() -> RecommendationService:
    try:
        loader = DataLoader()
        books_df, _, ratings_df = loader.load_all(sample_ratings=150000)
        hybrid = None
        if books_df is not None and ratings_df is not None:
            hybrid = HybridRecommender(books_df, ratings_df, None, loader=loader)
    except Exception:
        books_df = pd.DataFrame()
        hybrid = None
    return RecommendationService(books_df=books_df, hybrid=hybrid)

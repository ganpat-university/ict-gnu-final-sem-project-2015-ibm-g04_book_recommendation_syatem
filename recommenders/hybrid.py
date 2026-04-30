"""
Hybrid Recommender — CF + Content-Based + Popularity fallback

scoring
-------
  score = alpha * cf_score + (1 - alpha) * content_score
  final  = score * (1 + recency_boost)

alpha selection (by user interaction count)
-------------------------------------------
  n_interactions >= 30  →  alpha = 0.85
  5–29                  →  alpha = 0.60
  1–4                   →  alpha = 0.40
  0 (new user)          →  alpha = 0.20  + popularity blend

Item cold-start adjustment
--------------------------
  If an item has < 5 ratings, CF score is down-weighted by 0.5.

Public API preserved for app.py
--------------------------------
  get_recommendations(user_id, book_id, n, weights, selected_genres)
  get_friend_recommendations(user_id, n)
  add_friends(user_id, friend_ids)
  get_because_you_read(user_id, n)
  recommend(user_id, book_id, n)
  .popularity   (sub-recommender, accessed by app.py routes)
  .content      (sub-recommender, accessed by app.py routes)
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import os

from .popularity import PopularityRecommender
from .content_based import ContentBasedRecommender
from .collaborative import CollaborativeRecommender
from .svd_adapter import SVDAdapter
from .ncf_adapter import NCFAdapter


# ---------------------------------------------------------------------------
# Alpha tiers
# ---------------------------------------------------------------------------
def _alpha_from_interactions(n: int) -> float:
    if n >= 30:
        return 0.85
    if n >= 5:
        return 0.60
    if n >= 1:
        return 0.40
    return 0.20   # new user / no history


class HybridRecommender:
    """
    Hybrid recommendation system: CF + Content-Based + Popularity fallback.

    Parameters
    ----------
    books_df   : book catalogue DataFrame
    ratings_df : user ratings DataFrame
    users_df   : optional user metadata
    loader     : DataLoader instance (passed to ContentBasedRecommender for tags)
    """

    def __init__(
        self,
        books_df: pd.DataFrame,
        ratings_df: pd.DataFrame,
        users_df: pd.DataFrame = None,
        loader=None,
    ):
        self.books_df = books_df
        self.ratings_df = ratings_df
        self.users_df = users_df
        self.loader = loader

        print("\n" + "=" * 60)
        print("🚀 INITIALISING HYBRID RECOMMENDER")
        print("=" * 60 + "\n")

        print("📊 Popularity recommender…")
        self.popularity = PopularityRecommender(books_df, ratings_df)

        print("\n📚 Content-based recommender…")
        self.content = ContentBasedRecommender(books_df, ratings_df, loader=loader)

        print("\n👥 Collaborative (ALS) recommender…")
        filtered = self._filter_ratings(ratings_df)
        self.collaborative = CollaborativeRecommender(filtered, books_df)
        self.enable_svd = os.environ.get("ENABLE_SAGEMAKER_SVD", "").strip().lower() in {"1", "true", "yes", "on"}
        self.enable_ncf = os.environ.get("ENABLE_NCF", "").strip().lower() in {"1", "true", "yes", "on"}
        self.svd = SVDAdapter(os.environ.get("SVD_ARTIFACT_S3_URI", "").strip(), books_df) if self.enable_svd else None
        self.ncf = NCFAdapter(os.environ.get("NCF_ARTIFACT_S3_URI", "").strip()) if self.enable_ncf else None

        # Pre-compute per-item rating counts for cold-start adjustment
        self._item_rating_counts: dict = (
            ratings_df.groupby("book_id")["rating"].count().to_dict()
        )

        # Friends map (populated via add_friends / app.py)
        self.friends_map: dict = {}

        print("\n" + "=" * 60)
        print("✓ HYBRID RECOMMENDER READY")
        print("=" * 60 + "\n")

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _filter_ratings(
        ratings_df: pd.DataFrame,
        min_user_ratings: int = 5,
        min_book_ratings: int = 5,
    ) -> pd.DataFrame:
        df = ratings_df.copy()
        uc = df["user_id"].value_counts()
        df = df[df["user_id"].isin(uc[uc >= min_user_ratings].index)]
        bc = df["book_id"].value_counts()
        df = df[df["book_id"].isin(bc[bc >= min_book_ratings].index)]
        print(f"  Filtered ratings: {len(ratings_df):,} → {len(df):,}")
        return df

    def get_user_history_count(self, user_id) -> int:
        return int((self.ratings_df["user_id"] == user_id).sum())

    def is_cold_start_user(self, user_id, threshold: int = 3) -> bool:
        return self.get_user_history_count(user_id) < threshold

    def _get_rated_book_ids(self, user_id) -> set:
        return set(
            self.ratings_df[self.ratings_df["user_id"] == user_id]["book_id"]
        )

    def _get_candidate_books(self, user_id, exclude_rated: bool = True) -> list:
        """Return all book IDs, optionally excluding already-rated ones."""
        all_ids = self.books_df["book_id"].tolist()
        if not exclude_rated:
            return all_ids
        rated = self._get_rated_book_ids(user_id)
        return [b for b in all_ids if b not in rated]

    # -----------------------------------------------------------------------
    # Core hybrid scoring
    # -----------------------------------------------------------------------

    def _hybrid_score_for_user(
        self, user_id, n: int = 10
    ) -> pd.DataFrame:
        """
        Compute hybrid scores for all unrated books and return the top-n.
        """
        n_interactions = self.get_user_history_count(user_id)
        alpha = _alpha_from_interactions(n_interactions)

        candidates = self._get_candidate_books(user_id)
        if not candidates:
            return pd.DataFrame()

        # --- CF scores ---
        cf_scores = self.collaborative.get_cf_scores(user_id, candidates)
        svd_scores = self.svd.get_scores(user_id, candidates) if self.svd is not None else {b: 0.0 for b in candidates}

        # --- Content scores (relative to user's most-rated book) ---
        user_ratings = self.ratings_df[self.ratings_df["user_id"] == user_id]
        content_scores: dict = {}
        if not user_ratings.empty:
            anchor_book = (
                user_ratings.sort_values("rating", ascending=False)
                .iloc[0]["book_id"]
            )
            content_scores = self.content.get_content_scores(anchor_book, candidates)
        else:
            content_scores = {b: 0.0 for b in candidates}

        # --- Recency boost ---
        boost = self.collaborative.get_recency_boost(user_id, candidates)

        # --- Popularity scores (for new-user blending) ---
        pop_lookup: dict = {}
        if alpha <= 0.20 and hasattr(self.popularity, "popularity_df"):
            pop_df = self.popularity.popularity_df
            if pop_df is not None and "weighted_rating" in pop_df.columns:
                col = "weighted_rating"
            elif pop_df is not None and "avg_rating" in pop_df.columns:
                col = "avg_rating"
            else:
                col = None

            if col and pop_df is not None:
                max_val = pop_df[col].max() or 1.0
                pop_lookup = dict(
                    zip(pop_df["book_id"], pop_df[col] / max_val)
                )

        # --- Combine ---
        rows = []
        for book_id in candidates:
            cf = cf_scores.get(book_id, 0.0)
            svd = svd_scores.get(book_id, 0.0)
            cont = content_scores.get(book_id, 0.0)
            rec_boost = boost.get(book_id, 0.0)

            # Down-weight CF for items with very few ratings
            n_item_ratings = self._item_rating_counts.get(book_id, 0)
            if n_item_ratings < 5:
                cf = cf * 0.5
                cont = cont * 1.5  # compensate with content

            model_cf = 0.7 * cf + 0.3 * svd if self.svd is not None else cf
            if alpha <= 0.20 and pop_lookup:
                pop = pop_lookup.get(book_id, 0.0)
                base = alpha * model_cf + (1 - alpha) * (0.6 * cont + 0.4 * pop)
            else:
                base = alpha * model_cf + (1 - alpha) * cont

            final = base * (1.0 + rec_boost)
            rows.append({"book_id": book_id, "final_score": final})

        if not rows:
            return pd.DataFrame()

        score_map = {int(r["book_id"]): float(r["final_score"]) for r in rows}
        if self.ncf is not None:
            score_map = self.ncf.rerank_scores(user_id=user_id, base_scores=score_map)

        result = pd.DataFrame(
            [{"book_id": bid, "final_score": sc} for bid, sc in score_map.items()]
        ).sort_values("final_score", ascending=False).head(n)
        result = result.merge(self.books_df, on="book_id", how="left")
        # Normalize for API/UI scoring consistency
        if not result.empty:
            lo, hi = result["final_score"].min(), result["final_score"].max()
            if hi > lo:
                result["score_norm"] = (result["final_score"] - lo) / (hi - lo)
            else:
                result["score_norm"] = 0.0
        else:
            result["score_norm"] = 0.0
        result["strategy"] = "hybrid"
        return result

    @staticmethod
    def _jaccard(a: list, b: list) -> float:
        sa = {str(x).lower() for x in (a or [])}
        sb = {str(x).lower() for x in (b or [])}
        if not sa or not sb:
            return 0.0
        inter = len(sa & sb)
        union = len(sa | sb)
        return inter / union if union else 0.0

    @staticmethod
    def _length_match(pref: str, book_len: str) -> float:
        if not pref or pref == "any":
            return 1.0
        return 1.0 if pref == book_len else 0.5

    def _explain(self, row: pd.Series, score_norm: float) -> tuple[list[str], list[str]]:
        reasons: list[str] = []
        title = row.get("title", "This book")
        rating = row.get("avg_rating")
        count = row.get("rating_count")
        if pd.notna(rating) and pd.notna(count):
            reasons.append(f"Beloved by readers ({float(rating):.2f}★ over {int(count):,} ratings)")
        reasons.append(f"Recommended by hybrid intelligence for {title}")

        badges: list[str] = []
        if score_norm >= 0.85:
            badges.append("Top Pick")
        if pd.notna(count) and int(count) >= 50000:
            badges.append("Bestseller")
        if pd.notna(count) and int(count) >= 20000:
            badges.append("Reader Favorite")
        if score_norm >= 0.70:
            badges.append("Strong Match")
        if not badges:
            badges.append("Recommended")
        return reasons, badges

    # -----------------------------------------------------------------------
    # Public API  (preserves signatures called by app.py)
    # -----------------------------------------------------------------------

    def get_recommendations(
        self,
        user_id=None,
        book_id: int = None,
        n: int = 10,
        weights: dict = None,       # kept for signature compat, unused
        selected_genres: list = None,
    ) -> pd.DataFrame:
        """
        Main recommendation entry-point.

        * user_id supplied  → personalised hybrid scoring
        * book_id supplied  → content-similar books
        * Neither           → popularity fallback
        """
        if user_id is not None:
            n_interactions = self.get_user_history_count(user_id)

            # Strict new-user cold-start: return popularity
            if n_interactions == 0:
                pop = self.popularity.get_best_books(n=n)
                if pop is not None and not pop.empty:
                    pop = pop.copy()
                    pop["strategy"] = "popularity"
                    # Genre filter for cold-start
                    if selected_genres and self.loader:
                        try:
                            tag_ids = self.loader.tags_df[
                                self.loader.tags_df["tag_name"].isin(selected_genres)
                            ]["tag_id"]
                            gids = self.loader.book_tags_df[
                                self.loader.book_tags_df["tag_id"].isin(tag_ids)
                            ]["goodreads_book_id"].unique()
                            genre_bids = self.books_df[
                                self.books_df["goodreads_book_id"].isin(gids)
                            ]["book_id"]
                            pop = pop[pop["book_id"].isin(genre_bids)].head(n)
                        except Exception:
                            pop = pop.head(n)
                return pop

            return self._hybrid_score_for_user(user_id, n)

        if book_id is not None:
            sims = self.content.get_similar_to_book(book_id, n)
            if sims is not None and not sims.empty:
                sims = sims.copy()
                sims["strategy"] = "content"
            return sims

        # Fallback: popularity
        pop = self.popularity.get_best_books(n=n)
        if pop is not None and not pop.empty:
            pop = pop.copy()
            pop["strategy"] = "popularity"
        return pop

    def get_recommendations_explained(
        self,
        user_id=None,
        n: int = 12,
        read_book_ids: list | None = None,
    ) -> list[dict]:
        """
        Deterministic recommendation payload for API/UI:
        [{book, score, reasons[], badges[]}]
        """
        recs = self.get_recommendations(user_id=user_id, n=max(50, n))
        if recs is None or recs.empty:
            return []

        read_set = {int(x) for x in (read_book_ids or []) if str(x).isdigit()}
        if read_set:
            recs = recs[~recs["book_id"].isin(read_set)]

        if "score_norm" not in recs.columns:
            if "final_score" in recs.columns:
                lo, hi = recs["final_score"].min(), recs["final_score"].max()
                recs["score_norm"] = ((recs["final_score"] - lo) / (hi - lo)) if hi > lo else 0.0
            elif "weighted_rating" in recs.columns:
                lo, hi = recs["weighted_rating"].min(), recs["weighted_rating"].max()
                recs["score_norm"] = ((recs["weighted_rating"] - lo) / (hi - lo)) if hi > lo else 0.0
            else:
                recs["score_norm"] = 0.5

        out: list[dict] = []
        for _, row in recs.head(n).iterrows():
            score_norm = float(row.get("score_norm", 0.0))
            reasons, badges = self._explain(row, score_norm)
            book = {
                "book_id": int(row.get("book_id")) if pd.notna(row.get("book_id")) else None,
                "title": row.get("title"),
                "author": row.get("author"),
                "year": int(row.get("year")) if pd.notna(row.get("year")) else None,
                "avg_rating": float(row.get("avg_rating")) if pd.notna(row.get("avg_rating")) else None,
                "rating_count": int(row.get("rating_count")) if pd.notna(row.get("rating_count")) else None,
                "image_url_m": row.get("image_url_m"),
            }
            out.append(
                {
                    "book": book,
                    "score": round(score_norm * 100, 2),
                    "reasons": reasons,
                    "badges": badges,
                }
            )
        return out

    # -----------------------------------------------------------------------
    # Friend recommendations  (used by app.py /api/recommendations/friends)
    # -----------------------------------------------------------------------

    def add_friends(self, user_id, friend_ids: list):
        self.friends_map[user_id] = list(friend_ids)

    def get_friend_recommendations(self, user_id, n: int = 10) -> pd.DataFrame:
        friends = self.friends_map.get(user_id, [])
        if not friends:
            return pd.DataFrame()

        friend_ratings = self.ratings_df[
            self.ratings_df["user_id"].isin(friends)
        ]
        if friend_ratings.empty:
            return pd.DataFrame()

        user_rated = self._get_rated_book_ids(user_id)
        friend_books = (
            friend_ratings.groupby("book_id")
            .agg(avg_rating=("rating", "mean"), friend_count=("user_id", "nunique"))
            .reset_index()
        )
        friend_books["score"] = (
            friend_books["avg_rating"] * 0.5 + friend_books["friend_count"] * 0.5
        )
        friend_books = friend_books[
            ~friend_books["book_id"].isin(user_rated)
        ].sort_values("score", ascending=False)

        result = friend_books.head(n).merge(self.books_df, on="book_id", how="left")
        return result

    # -----------------------------------------------------------------------
    # "Because you read…"  (used by app.py /api/recommendations/personalized)
    # -----------------------------------------------------------------------

    def get_because_you_read(self, user_id, n: int = 10) -> dict:
        user_ratings = self.ratings_df[
            self.ratings_df["user_id"] == user_id
        ].sort_values("rating", ascending=False)

        if user_ratings.empty:
            return {}

        top_books = user_ratings.head(3)
        result = {}
        for _, row in top_books.iterrows():
            book_id = row["book_id"]
            book_info = self.books_df[self.books_df["book_id"] == book_id]
            if not book_info.empty:
                title = book_info.iloc[0].get("title", str(book_id))
                similar = self.content.get_similar_to_book(book_id, n=n // 3 or 3)
                result[title] = similar

        return result

    # -----------------------------------------------------------------------
    # Convenience wrapper
    # -----------------------------------------------------------------------

    def recommend(self, user_id=None, book_id=None, n: int = 10) -> pd.DataFrame:
        return self.get_recommendations(user_id=user_id, book_id=book_id, n=n)


if __name__ == "__main__":
    import sys
    sys.path.append("..")
    from data_loader import DataLoader

    loader = DataLoader()
    books, users, ratings = loader.load_all()

    if books is not None and ratings is not None:
        hybrid = HybridRecommender(books, ratings, users, loader=loader)

        test_user = ratings["user_id"].value_counts().index[0]
        print(f"\nHybrid recs for warm user {test_user}:")
        print(hybrid.get_recommendations(user_id=test_user, n=5))

        # Cold-start
        fake_new_user = -999
        print(f"\nCold-start recs (new user {fake_new_user}):")
        print(hybrid.get_recommendations(user_id=fake_new_user, n=5))

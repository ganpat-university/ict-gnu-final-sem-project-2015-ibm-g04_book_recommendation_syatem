"""
Collaborative Filtering Recommender — Vectorized ALS (Gramian approach)

Implements the standard weighted-regularized ALS for implicit feedback using
vectorized numpy matrix operations — no per-user Python loops beyond the
per-entity linear solve, no external C extensions required.

The model is cached to disk after the first training run (keyed by dataset
fingerprint) so subsequent app restarts skip retraining entirely.

Public API
----------
  get_cf_scores(user_id, candidate_book_ids)       → dict {book_id: score}
  get_item_neighbors(book_id, k=50)                → list [(book_id, sim)]
  get_recency_boost(user_id, candidates, last_n=5) → dict {book_id: boost}
"""

from __future__ import annotations

import hashlib
import os
import pickle

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix


class CollaborativeRecommender:
    """
    Implicit-feedback ALS using the vectorized Gramian approach.

    Parameters
    ----------
    ratings_df        : DataFrame  (user_id, book_id, rating)
    books_df          : Optional book info DataFrame
    factors           : latent dimension        (default 64)
    regularization    : L2 lambda               (default 0.01)
    iterations        : ALS sweeps              (default 5)  — 5 gives
                        good quality; increase to 10–20 for best accuracy
    alpha_confidence  : c = 1 + alpha * rating  (default 10.0)
    cache_path        : Directory to cache trained factors (default 'data/')
    """

    def __init__(
        self,
        ratings_df: pd.DataFrame,
        books_df: pd.DataFrame = None,
        factors: int = 64,
        regularization: float = 0.01,
        iterations: int = 5,
        alpha_confidence: float = 10.0,
        cache_path: str = "data",
    ):
        self.ratings_df = ratings_df.copy()
        self.books_df = books_df
        self.factors = factors
        self.regularization = regularization
        self.iterations = iterations
        self.alpha_confidence = alpha_confidence
        self.cache_path = cache_path

        self.user_item_matrix: csr_matrix | None = None
        self.item_user_matrix: csr_matrix | None = None

        self.user_to_idx: dict = {}
        self.idx_to_user: dict = {}
        self.item_to_idx: dict = {}
        self.idx_to_item: dict = {}

        self._user_factors: np.ndarray | None = None  # (n_users × factors)
        self._item_factors: np.ndarray | None = None  # (n_items × factors)

        self._prepare_data()
        self._train()

    # -----------------------------------------------------------------------
    # Data preparation
    # -----------------------------------------------------------------------

    def _prepare_data(self):
        df = self.ratings_df
        if df is None or df.empty:
            print("CollaborativeRecommender: no ratings data.")
            return

        print("Building ALS confidence matrix…")

        unique_users = df["user_id"].unique()
        unique_items = df["book_id"].unique()

        self.user_to_idx = {u: i for i, u in enumerate(unique_users)}
        self.idx_to_user = {i: u for u, i in self.user_to_idx.items()}
        self.item_to_idx = {it: i for i, it in enumerate(unique_items)}
        self.idx_to_item = {i: it for it, i in self.item_to_idx.items()}

        print(f"  Users: {len(unique_users):,} | Items: {len(unique_items):,}")

        rows = df["user_id"].map(self.user_to_idx)
        cols = df["book_id"].map(self.item_to_idx)
        confidence = (1.0 + self.alpha_confidence * df["rating"]).astype(np.float32)

        valid = rows.notna() & cols.notna()
        r = rows[valid].astype(int).values
        c = cols[valid].astype(int).values
        d = confidence[valid].values

        n_users = len(self.user_to_idx)
        n_items = len(self.item_to_idx)

        # user × item sparse confidence matrix (entries where rating exists)
        self.user_item_matrix = csr_matrix(
            (d, (r, c)), shape=(n_users, n_items), dtype=np.float32
        )
        # item × user view
        self.item_user_matrix = self.user_item_matrix.T.tocsr()
        print(f"  ✓ Confidence matrix: {self.user_item_matrix.shape}, "
              f"density={self.user_item_matrix.nnz / (n_users * n_items):.5f}")

    # -----------------------------------------------------------------------
    # Vectorized ALS — Gramian approach
    # -----------------------------------------------------------------------

    def _solve_als(
        self,
        confidence_matrix: csr_matrix,
        fixed_factors: np.ndarray,
        regularization: float,
    ) -> np.ndarray:
        """
        Solve one side of ALS given the other side's fixed factors.

        For each entity u (row of confidence_matrix), solve:
            x_u = (Y^T Y + Y^T diag(c_u - 1) Y + λI)^{-1} (Y^T c_u)

        Parameters
        ----------
        confidence_matrix : sparse (n_entities × n_others)  — C values
        fixed_factors     : ndarray (n_others × factors)    — Y
        regularization    : float                           — λ

        Returns
        -------
        ndarray (n_entities × factors)
        """
        n_entities = confidence_matrix.shape[0]
        n_factors = fixed_factors.shape[1]

        # Precompute global Gramian: Y^T Y  (factors × factors)
        YtY = fixed_factors.T @ fixed_factors  # (f × f)
        lam_I = regularization * np.eye(n_factors, dtype=np.float32)
        base = YtY + lam_I  # (f × f) — same for all entities

        solved = np.zeros((n_entities, n_factors), dtype=np.float32)

        for u in range(n_entities):
            row = confidence_matrix[u]  # 1 × n_others  (sparse)
            if row.nnz == 0:
                continue

            indices = row.indices          # item indices where c > 0
            conf_u  = row.data             # c_ui values

            # Y_u: (nnz × f) sub-matrix of fixed factors for rated items
            Y_u = fixed_factors[indices]   # (nnz × f)

            # Additional term: Y_u^T diag(c_u - 1) Y_u
            # = (Y_u * (c_u - 1)[:, None]).T @ Y_u
            delta = conf_u - 1.0
            A = base + (Y_u * delta[:, None]).T @ Y_u  # (f × f)

            # RHS: Y_u^T c_u  (preference p_ui = 1 always)
            b = (Y_u * conf_u[:, None]).sum(axis=0)   # (f,)

            # Solve linear system Ax = b
            try:
                solved[u] = np.linalg.solve(A, b)
            except np.linalg.LinAlgError:
                solved[u] = np.linalg.lstsq(A, b, rcond=None)[0]

        return solved

    def _cache_key(self) -> str:
        """Compute a fingerprint for the current dataset + hyperparameters."""
        sig = (
            f"{len(self.ratings_df)}_"
            f"{self.ratings_df['user_id'].nunique()}_"
            f"{self.ratings_df['book_id'].nunique()}_"
            f"{self.factors}_{self.regularization}_{self.iterations}_"
            f"{self.alpha_confidence}"
        )
        return hashlib.md5(sig.encode()).hexdigest()[:12]

    def _cache_file(self) -> str:
        return os.path.join(self.cache_path, f"als_factors_{self._cache_key()}.pkl")

    def _load_cache(self) -> bool:
        """Try to load pre-trained factors from disk. Returns True if loaded."""
        path = self._cache_file()
        if not os.path.exists(path):
            return False
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self.user_to_idx = data["user_to_idx"]
            self.idx_to_user = data["idx_to_user"]
            self.item_to_idx = data["item_to_idx"]
            self.idx_to_item = data["idx_to_item"]
            self._user_factors = data["user_factors"]
            self._item_factors = data["item_factors"]
            print(f"  ✓ Loaded cached ALS factors from {path}")
            return True
        except Exception as exc:
            print(f"  Cache load failed ({exc}), retraining…")
            return False

    def _save_cache(self):
        """Persist trained factors to disk."""
        os.makedirs(self.cache_path, exist_ok=True)
        path = self._cache_file()
        with open(path, "wb") as f:
            pickle.dump({
                "user_to_idx":  self.user_to_idx,
                "idx_to_user":  self.idx_to_user,
                "item_to_idx":  self.item_to_idx,
                "idx_to_item":  self.idx_to_item,
                "user_factors": self._user_factors,
                "item_factors": self._item_factors,
            }, f)
        print(f"  ✓ ALS factors cached to {path}")

    def _train(self):
        """Train or load cached ALS model."""
        if self.user_item_matrix is None:
            return

        # Try cache first (skip expensive training on repeated runs)
        if self._load_cache():
            return

        n_users, n_items = self.user_item_matrix.shape
        rng = np.random.default_rng(42)

        print(f"Training ALS (factors={self.factors}, "
              f"reg={self.regularization}, iters={self.iterations})…")

        # Initialise factors
        X = rng.standard_normal((n_users, self.factors)).astype(np.float32) * 0.01
        Y = rng.standard_normal((n_items, self.factors)).astype(np.float32) * 0.01

        for it in range(self.iterations):
            # Update user factors (fix Y, solve for X)
            X = self._solve_als(self.user_item_matrix, Y, self.regularization)
            # Update item factors (fix X, solve for Y)
            Y = self._solve_als(self.item_user_matrix, X, self.regularization)

            if (it + 1) % 5 == 0 or it == 0:
                print(f"  ALS iteration {it + 1}/{self.iterations}")

        self._user_factors = X
        self._item_factors = Y
        print("✓ ALS training complete.")
        self._save_cache()

    # -----------------------------------------------------------------------
    # Public scoring API
    # -----------------------------------------------------------------------

    def get_cf_scores(
        self, user_id: int, candidate_book_ids: list
    ) -> dict:
        """
        CF scores (dot product in latent space) normalised to [0, 1].

        Returns dict {book_id: float}.
        """
        if self._user_factors is None or not candidate_book_ids:
            return {b: 0.0 for b in candidate_book_ids}

        if user_id not in self.user_to_idx:
            return {b: 0.0 for b in candidate_book_ids}

        u_idx = self.user_to_idx[user_id]
        u_vec = self._user_factors[u_idx]

        scores = {}
        for book_id in candidate_book_ids:
            if book_id in self.item_to_idx:
                i_idx = self.item_to_idx[book_id]
                scores[book_id] = float(np.dot(u_vec, self._item_factors[i_idx]))
            else:
                scores[book_id] = 0.0

        vals = list(scores.values())
        lo, hi = min(vals), max(vals)
        if hi > lo:
            scores = {k: (v - lo) / (hi - lo) for k, v in scores.items()}
        else:
            scores = {k: 0.0 for k in scores}

        return scores

    def get_item_neighbors(self, book_id: int, k: int = 50) -> list:
        """
        Top-k most similar items in MF factor space (cosine similarity).

        Returns list[(neighbor_book_id, cosine_sim)] sorted descending.
        """
        if self._item_factors is None or book_id not in self.item_to_idx:
            return []

        i_idx = self.item_to_idx[book_id]
        i_vec = self._item_factors[i_idx]
        norm_i = np.linalg.norm(i_vec)
        if norm_i == 0:
            return []

        norms = np.linalg.norm(self._item_factors, axis=1)
        norms[norms == 0] = 1e-9
        sims = self._item_factors.dot(i_vec) / (norms * norm_i)
        sims[i_idx] = -1.0  # exclude self

        k_actual = min(k, len(sims))
        top_indices = np.argpartition(sims, -k_actual)[-k_actual:]
        top_indices = top_indices[np.argsort(sims[top_indices])[::-1]]

        return [
            (self.idx_to_item[idx], float(sims[idx]))
            for idx in top_indices
            if sims[idx] > 0
        ]

    def get_recency_boost(
        self,
        user_id: int,
        candidate_book_ids: list,
        last_n: int = 5,
        half_life: float = 5.0,
    ) -> dict:
        """
        Exponential-decay recency boost.

        The user's most recent `last_n` rated items serve as anchors.
        Each candidate's boost = decay-weighted average cosine similarity
        to those anchors in MF space.

        Returns dict {book_id: float} in [0, 1].
        """
        if self._item_factors is None or not candidate_book_ids:
            return {b: 0.0 for b in candidate_book_ids}

        user_ratings = self.ratings_df[self.ratings_df["user_id"] == user_id]
        if user_ratings.empty:
            return {b: 0.0 for b in candidate_book_ids}

        # Most recent last → reverse to get rank-0 = most recent
        recent_books = user_ratings.tail(last_n)["book_id"].tolist()[::-1]
        decay = np.array(
            [np.exp(-rank / half_life) for rank in range(len(recent_books))],
            dtype=np.float32,
        )

        boost = {}
        for cand in candidate_book_ids:
            if cand not in self.item_to_idx:
                boost[cand] = 0.0
                continue

            c_idx = self.item_to_idx[cand]
            c_vec = self._item_factors[c_idx]
            c_norm = np.linalg.norm(c_vec)
            if c_norm == 0:
                boost[cand] = 0.0
                continue

            weighted_sim = 0.0
            total_w = 0.0
            for rank, src in enumerate(recent_books):
                if src not in self.item_to_idx:
                    continue
                s_idx = self.item_to_idx[src]
                s_vec = self._item_factors[s_idx]
                s_norm = np.linalg.norm(s_vec)
                if s_norm == 0:
                    continue
                sim = float(np.dot(c_vec, s_vec) / (c_norm * s_norm))
                w = decay[rank]
                weighted_sim += w * max(sim, 0.0)
                total_w += w

            boost[cand] = weighted_sim / total_w if total_w > 0 else 0.0

        return boost

    # -----------------------------------------------------------------------
    # Convenience wrapper
    # -----------------------------------------------------------------------

    def recommend(self, user_id: int = None, n: int = 10) -> pd.DataFrame:
        """Convenience: top-n CF recs for a user (excludes already-rated)."""
        if self._item_factors is None or user_id is None:
            return pd.DataFrame()

        rated = set(
            self.ratings_df[self.ratings_df["user_id"] == user_id]["book_id"]
        )
        candidates = [b for b in self.item_to_idx if b not in rated]
        scores = self.get_cf_scores(user_id, candidates)
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:n]

        recs = pd.DataFrame(top, columns=["book_id", "cf_score"])
        if self.books_df is not None:
            recs = recs.merge(self.books_df, on="book_id", how="left")
        return recs


if __name__ == "__main__":
    from data_loader import DataLoader

    loader = DataLoader()
    books, _, ratings = loader.load_all()

    if ratings is not None and books is not None:
        rec = CollaborativeRecommender(ratings, books, iterations=5)
        test_user = ratings["user_id"].value_counts().index[0]
        print(f"\nCF recs for user {test_user}:")
        print(rec.recommend(test_user, n=5))

        test_book = ratings["book_id"].value_counts().index[0]
        print(f"\nItem neighbours for book_id {test_book}:")
        print(rec.get_item_neighbors(test_book, k=5))

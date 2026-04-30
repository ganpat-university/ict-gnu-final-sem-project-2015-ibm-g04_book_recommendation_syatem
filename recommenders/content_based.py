"""
Content-Based Recommender — TF-IDF on title + tags

Builds TF-IDF vectors from each book's title combined with its top-15 tags
(joined from tags.csv + book_tags.csv).  Exposes cosine-similarity scoring
and a lightweight search helper used by the Flask app.

Parameters
----------
  ngram_range  : (1, 2)  — unigrams and bigrams
  max_features : 50_000
  min_df       : 2
  stop_words   : 'english'
"""

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class ContentBasedRecommender:
    """
    Content-based recommender using TF-IDF on book title + tag metadata.

    Primary methods
    ---------------
    get_content_scores(book_id, candidate_book_ids)
        Returns {book_id: cosine_similarity} for candidates vs. the source book.

    get_similar_to_book(book_id, n=10)
        Returns a DataFrame of the n most similar books.

    search_books(query, n=10)
        Title / author substring search (unchanged from original).

    Compatibility aliases (used by app.py / hybrid.py)
    ---------------------------------------------------
    get_similar_by_author(author, n, exclude_book_id)   ← kept for author tab
    """

    def __init__(self, books_df: pd.DataFrame, ratings_df=None, loader=None):
        self.books_df = books_df.copy()
        self.ratings_df = ratings_df
        self.loader = loader

        self.tfidf_vectorizer: TfidfVectorizer | None = None
        self.tfidf_matrix = None          # sparse (n_books × n_features)

        # Map book_id → row index in tfidf_matrix
        self._book_id_to_row: dict = {}

        self._prepare_data()

    # -----------------------------------------------------------------------
    # Preparation
    # -----------------------------------------------------------------------

    def _prepare_data(self):
        """Build TF-IDF matrix from title + tags."""
        if self.books_df is None or self.books_df.empty:
            print("ContentBasedRecommender: no books data.")
            return

        # Reset index so iloc positions are contiguous
        self.books_df = self.books_df.reset_index(drop=True)

        # Basic text fields
        self.books_df["clean_title"] = (
            self.books_df["title"].fillna("").str.lower()
        )
        self.books_df["clean_author"] = (
            self.books_df.get("author", pd.Series(dtype=str))
            .fillna("unknown").str.lower()
        )

        # --- Enrich with tags ---
        self.books_df["tags_str"] = ""
        if (
            self.loader is not None
            and hasattr(self.loader, "book_tags_df")
            and self.loader.book_tags_df is not None
            and hasattr(self.loader, "tags_df")
            and self.loader.tags_df is not None
        ):
            print("  Enriching content with tags…")
            try:
                bt = self.loader.book_tags_df.merge(
                    self.loader.tags_df, on="tag_id"
                )
                # Keep top-15 tags per book by count
                bt = (
                    bt.sort_values("count", ascending=False)
                    .groupby("goodreads_book_id")
                    .head(15)
                )
                book_tags_str = (
                    bt.groupby("goodreads_book_id")["tag_name"]
                    .apply(lambda x: " ".join(x))
                    .reset_index()
                    .rename(columns={"tag_name": "tags_content"})
                )
                self.books_df = self.books_df.merge(
                    book_tags_str, on="goodreads_book_id", how="left"
                )
                self.books_df["tags_str"] = (
                    self.books_df["tags_content"].fillna("").str.lower()
                )
                self.books_df = self.books_df.drop("tags_content", axis=1)
                print("  ✓ Tags integrated")
            except Exception as exc:
                print(f"  ✗ Tags error: {exc}")

        # Combined content = title + tags  (author not included in TF-IDF but
        # kept for the compat alias get_similar_by_author)
        self.books_df["content"] = (
            self.books_df["clean_title"] + " " + self.books_df["tags_str"]
        )

        # Build book_id → row mapping
        self._book_id_to_row = {
            row["book_id"]: idx
            for idx, row in self.books_df.iterrows()
        }

        self._build_tfidf_matrix()
        print(f"✓ Content-based recommender ready ({len(self.books_df):,} books)")

    def _build_tfidf_matrix(self):
        """Fit TF-IDF vectoriser on book content."""
        try:
            self.tfidf_vectorizer = TfidfVectorizer(
                stop_words="english",
                ngram_range=(1, 2),
                max_features=50_000,
                min_df=2,
            )
            self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(
                self.books_df["content"]
            )
            print(f"  ✓ TF-IDF matrix: {self.tfidf_matrix.shape}")
        except Exception as exc:
            print(f"  ✗ TF-IDF build error: {exc}")

    # -----------------------------------------------------------------------
    # Core scoring
    # -----------------------------------------------------------------------

    def get_content_scores(
        self, book_id: int, candidate_book_ids: list
    ) -> dict:
        """
        Cosine similarity between `book_id` and each candidate.

        Returns
        -------
        dict  {book_id: float}  — values in [0, 1]
        """
        if self.tfidf_matrix is None or not candidate_book_ids:
            return {b: 0.0 for b in candidate_book_ids}

        if book_id not in self._book_id_to_row:
            return {b: 0.0 for b in candidate_book_ids}

        src_row = self._book_id_to_row[book_id]
        src_vec = self.tfidf_matrix[src_row]

        scores = {}
        for cand in candidate_book_ids:
            if cand not in self._book_id_to_row:
                scores[cand] = 0.0
            else:
                cand_row = self._book_id_to_row[cand]
                sim = cosine_similarity(src_vec, self.tfidf_matrix[cand_row])[0, 0]
                scores[cand] = float(sim)

        return scores

    # -----------------------------------------------------------------------
    # DataFrame-level helpers
    # -----------------------------------------------------------------------

    def get_similar_to_book(self, book_id: int, n: int = 10) -> pd.DataFrame:
        """
        Return the n most content-similar books (excluding the source).
        """
        if self.tfidf_matrix is None:
            return pd.DataFrame()
        if book_id not in self._book_id_to_row:
            print(f"book_id {book_id} not in content index")
            return pd.DataFrame()

        src_row = self._book_id_to_row[book_id]
        sims = cosine_similarity(
            self.tfidf_matrix[src_row], self.tfidf_matrix
        ).flatten()
        sims[src_row] = -1.0  # exclude self

        top_idxs = np.argsort(sims)[::-1][:n]
        result = self.books_df.iloc[top_idxs].copy()
        result["similarity_score"] = sims[top_idxs]

        out_cols = [
            "book_id", "title", "author", "similarity_score",
            "image_url_m", "avg_rating",
        ]
        return result[[c for c in out_cols if c in result.columns]]

    # -----------------------------------------------------------------------
    # Compatibility alias — used by app.py author tab
    # -----------------------------------------------------------------------

    def get_similar_by_author(
        self, author: str, n: int = 10, exclude_book_id=None
    ) -> pd.DataFrame:
        """Return books by the same (partial-match) author, sorted by rating."""
        if self.books_df is None:
            return pd.DataFrame()

        mask = self.books_df["clean_author"].str.contains(
            author.lower(), na=False
        )
        result = self.books_df[mask].copy()

        if exclude_book_id is not None:
            result = result[result["book_id"] != exclude_book_id]

        sort_col = (
            "avg_rating" if "avg_rating" in result.columns else "clean_title"
        )
        result = result.sort_values(sort_col, ascending=False)

        out_cols = ["book_id", "title", "author", "avg_rating", "image_url_m"]
        return result.head(n)[[c for c in out_cols if c in result.columns]]

    # -----------------------------------------------------------------------
    # Search (unchanged functionality)
    # -----------------------------------------------------------------------

    def search_books(self, query: str, n: int = 10) -> pd.DataFrame:
        """Title / author substring search (literal, regex-safe)."""
        if self.books_df is None:
            return pd.DataFrame()

        q = query.lower()
        try:
            mask = (
                self.books_df["clean_title"].str.contains(q, na=False, regex=False)
                | self.books_df["clean_author"].str.contains(q, na=False, regex=False)
            )
            matches = self.books_df[mask]
        except Exception as exc:
            print(f"Search error: {exc}")
            return pd.DataFrame()

        out_cols = [
            "book_id", "title", "author", "year",
            "publisher", "image_url_m", "image_url_l", "avg_rating",
        ]
        return matches.head(n)[[c for c in out_cols if c in matches.columns]]

    # -----------------------------------------------------------------------
    # Convenience wrapper
    # -----------------------------------------------------------------------

    def recommend(self, book_id=None, author=None, n=10) -> pd.DataFrame:
        if book_id:
            return self.get_similar_to_book(book_id, n)
        if author:
            return self.get_similar_by_author(author, n)
        # Deterministic fallback: top-rated books (never random output).
        sort_col = "avg_rating" if "avg_rating" in self.books_df.columns else "title"
        result = self.books_df.sort_values(sort_col, ascending=False).head(min(n, len(self.books_df)))
        out_cols = ["book_id", "title", "author", "image_url_m", "avg_rating"]
        return result[[c for c in out_cols if c in result.columns]]


if __name__ == "__main__":
    from data_loader import DataLoader

    loader = DataLoader()
    books, _, ratings = loader.load_all()

    if books is not None:
        rec = ContentBasedRecommender(books, ratings, loader=loader)
        print("\nSearch 'harry potter':")
        print(rec.search_books("harry potter", 5))

        results = rec.search_books("harry potter", 1)
        if not results.empty:
            bid = results.iloc[0]["book_id"]
            print(f"\nSimilar to book_id {bid}:")
            print(rec.get_similar_to_book(bid, 5))

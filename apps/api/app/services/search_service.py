from functools import lru_cache

import pandas as pd


class SearchService:
    def __init__(self, books_df: pd.DataFrame | None = None):
        self.books_df = books_df if books_df is not None else pd.DataFrame()

    def search(self, q: str, limit: int = 20):
        if self.books_df.empty:
            return []
        query = q.strip().lower()
        if not query:
            return []
        mask = (
            self.books_df["title"].fillna("").str.lower().str.contains(query, regex=False)
            | self.books_df["author"].fillna("").str.lower().str.contains(query, regex=False)
        )
        out = self.books_df.loc[mask, ["book_id", "title", "author"]].head(limit)
        return out.to_dict("records")

    def suggest(self, q: str, limit: int = 8):
        return self.search(q, limit=limit)


@lru_cache(maxsize=1)
def get_search_service() -> SearchService:
    try:
        books_df = pd.read_csv("data/books.csv")
    except Exception:
        books_df = pd.DataFrame()
    return SearchService(books_df=books_df)

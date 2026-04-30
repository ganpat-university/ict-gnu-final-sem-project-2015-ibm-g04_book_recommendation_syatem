"""
Popularity-Based Recommender

Adapted from:
- syedsharin/Book-Recommendation-System-Project: Rating-based popularity
- nikunjsonule/Book-Recommendation-System: Top-rated books

Ideal for:
- Cold-start users (no rating history)
- Trending/bestseller sections
- Fallback recommendations
"""

import pandas as pd
import numpy as np


class PopularityRecommender:
    """
    Recommends books based on popularity metrics.
    
    Strategies:
    1. Average Rating: Books with highest average ratings
    2. Rating Count: Most-rated books
    3. Weighted Rating: Combines average and count (like IMDB formula)
    """
    
    def __init__(self, books_df, ratings_df):
        """
        Initialize with books and ratings data.
        
        Args:
            books_df: DataFrame with book information
            ratings_df: DataFrame with user ratings
        """
        self.books_df = books_df.copy() if books_df is not None else None
        self.ratings_df = ratings_df
        self.popularity_df = None
        self._build_popularity_scores()
    
    def _build_popularity_scores(self):
        """Calculate popularity scores for all books."""
        if self.books_df is None:
            print("Error: Missing books data for popularity calculation")
            return
        
        # Check if books already have pre-computed ratings (goodbooks-10k)
        has_precomputed = 'avg_rating' in self.books_df.columns and 'rating_count' in self.books_df.columns
        
        if has_precomputed:
            # Use pre-computed ratings from books.csv
            self.popularity_df = self.books_df.copy()
            print("  ✓ Using pre-computed ratings from books data")
        elif self.ratings_df is not None:
            # Compute from ratings
            book_stats = self.ratings_df.groupby('book_id').agg(
                avg_rating=('rating', 'mean'),
                rating_count=('rating', 'count'),
                total_rating=('rating', 'sum')
            ).reset_index()
            
            # Merge with book info
            self.popularity_df = book_stats.merge(
                self.books_df, 
                on='book_id', 
                how='left'
            )
        else:
            print("Error: No ratings data available")
            return
        
        # Calculate weighted rating (IMDB formula variant)
        # WR = (v/(v+m)) * R + (m/(v+m)) * C
        if 'avg_rating' in self.popularity_df.columns and 'rating_count' in self.popularity_df.columns:
            C = self.popularity_df['avg_rating'].mean()  # Global average
            m = self.popularity_df['rating_count'].quantile(0.75)  # 75th percentile as threshold
            
            def weighted_rating(row, m=m, C=C):
                v = row['rating_count']
                R = row['avg_rating']
                if pd.isna(v) or pd.isna(R) or v == 0:
                    return 0
                return (v / (v + m)) * R + (m / (v + m)) * C
            
            self.popularity_df['weighted_rating'] = self.popularity_df.apply(weighted_rating, axis=1)
        
        print(f"✓ Built popularity scores for {len(self.popularity_df):,} books")
    
    def get_top_rated(self, n=10, min_ratings=10):
        """
        Get books with highest average ratings.
        
        Args:
            n: Number of recommendations
            min_ratings: Minimum number of ratings required
            
        Returns:
            DataFrame with top-rated books
        """
        if self.popularity_df is None:
            return pd.DataFrame()
        
        df = self.popularity_df.copy()
        
        if 'rating_count' in df.columns:
            df = df[df['rating_count'] >= min_ratings]
        
        # Get available columns
        result_cols = ['book_id', 'title', 'author', 'avg_rating', 'rating_count', 'image_url_m']
        available_cols = [c for c in result_cols if c in df.columns]
        
        return df.nlargest(n, 'avg_rating')[available_cols]
    
    def get_most_popular(self, n=10):
        """
        Get most-rated books (highest interaction count).
        
        Args:
            n: Number of recommendations
            
        Returns:
            DataFrame with most popular books
        """
        if self.popularity_df is None:
            return pd.DataFrame()
        
        df = self.popularity_df.copy()
        
        sort_col = 'rating_count' if 'rating_count' in df.columns else 'avg_rating'
        
        result_cols = ['book_id', 'title', 'author', 'avg_rating', 'rating_count', 'image_url_m']
        available_cols = [c for c in result_cols if c in df.columns]
        
        return df.nlargest(n, sort_col)[available_cols]
    
    def get_best_books(self, n=10, min_ratings=20):
        """
        Get best books using weighted rating (quality + popularity).
        
        Args:
            n: Number of recommendations
            min_ratings: Minimum ratings threshold
            
        Returns:
            DataFrame with best books
        """
        if self.popularity_df is None:
            return pd.DataFrame()
        
        df = self.popularity_df.copy()
        
        if 'rating_count' in df.columns:
            df = df[df['rating_count'] >= min_ratings]
        
        sort_col = 'weighted_rating' if 'weighted_rating' in df.columns else 'avg_rating'
        
        result_cols = ['book_id', 'title', 'author', 'avg_rating', 'rating_count', 
                       'weighted_rating', 'image_url_m']
        available_cols = [c for c in result_cols if c in df.columns]
        
        return df.nlargest(n, sort_col)[available_cols]
    
    def get_trending_by_year(self, year=None, n=10):
        """
        Get popular books from a specific publication year.
        
        Args:
            year: Publication year (None for recent years)
            n: Number of recommendations
            
        Returns:
            DataFrame with trending books
        """
        if self.popularity_df is None:
            return pd.DataFrame()
        
        df = self.popularity_df.copy()
        
        if year is not None:
            df = df[df['year'] == year]
        elif 'year' in df.columns:
            # Get recent books (last 10 years from max year)
            valid_years = df[df['year'] > 0]['year']
            if not valid_years.empty:
                max_year = valid_years.max()
                df = df[(df['year'] >= max_year - 10) & (df['year'] > 0)]
        
        sort_col = 'weighted_rating' if 'weighted_rating' in df.columns else 'avg_rating'
        
        result_cols = ['book_id', 'title', 'author', 'year', 'avg_rating', 'rating_count', 'image_url_m']
        available_cols = [c for c in result_cols if c in df.columns]
        
        return df.nlargest(n, sort_col)[available_cols]
    
    def get_top_by_author(self, author, n=5):
        """
        Get top books by a specific author.
        
        Args:
            author: Author name (partial match supported)
            n: Number of recommendations
            
        Returns:
            DataFrame with author's top books
        """
        if self.popularity_df is None:
            return pd.DataFrame()
        
        author_books = self.popularity_df[
            self.popularity_df['author'].str.contains(author, case=False, na=False)
        ]
        
        sort_col = 'weighted_rating' if 'weighted_rating' in author_books.columns else 'avg_rating'
        
        result_cols = ['book_id', 'title', 'author', 'avg_rating', 'rating_count', 'image_url_m']
        available_cols = [c for c in result_cols if c in author_books.columns]
        
        return author_books.nlargest(n, sort_col)[available_cols]
    
    def recommend(self, n=10, strategy='weighted'):
        """
        Get recommendations using specified strategy.
        
        Args:
            n: Number of recommendations
            strategy: 'top_rated', 'most_popular', or 'weighted'
            
        Returns:
            DataFrame with recommendations
        """
        strategies = {
            'top_rated': lambda: self.get_top_rated(n),
            'most_popular': lambda: self.get_most_popular(n),
            'weighted': lambda: self.get_best_books(n),
        }
        
        return strategies.get(strategy, strategies['weighted'])()


if __name__ == '__main__':
    # Test with sample data
    from data_loader import DataLoader
    
    loader = DataLoader()
    books, users, ratings = loader.load_all()
    
    if books is not None and ratings is not None:
        recommender = PopularityRecommender(books, ratings)
        
        print("\n📚 Top Rated Books:")
        print(recommender.get_top_rated(5))
        
        print("\n🔥 Most Popular Books:")
        print(recommender.get_most_popular(5))
        
        print("\n⭐ Best Books (Weighted):")
        print(recommender.get_best_books(5))

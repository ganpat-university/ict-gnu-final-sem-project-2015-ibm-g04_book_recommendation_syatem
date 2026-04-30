"""
Recommender modules package.

This package contains different recommendation algorithms:
- popularity: Trending and top-rated books
- content_based: Author and title similarity
- collaborative: User-user, item-item, and SVD-based recommendations
- hybrid: Combined weighted recommendations
"""

from .popularity import PopularityRecommender
from .content_based import ContentBasedRecommender
from .collaborative import CollaborativeRecommender
from .hybrid import HybridRecommender

__all__ = [
    'PopularityRecommender',
    'ContentBasedRecommender', 
    'CollaborativeRecommender',
    'HybridRecommender'
]

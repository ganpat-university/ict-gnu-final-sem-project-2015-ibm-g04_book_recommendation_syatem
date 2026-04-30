# NovelNest ML Workflow

## Data Pipeline
- Source tables/files: `users`, `books`, `ratings`, `interactions`.
- Build implicit signal from interactions:
  - `view` = 0.2
  - `click` = 0.5
  - `like` = 0.8
  - `rating` = explicit value
  - `dwell_ms` normalized boost
- Aggregate into `user_id, book_id, signal`.

## Training Flow
1. Train SVD baseline for fast robust recommendations.
2. Train NCF (embeddings + MLP) for non-linear user-item patterns.
3. Evaluate with `Precision@K`, `Recall@K`, `NDCG@K`.
4. Store artifact metadata and model payload in S3.

## Inference Logic
`final_score = 0.4 * svd + 0.35 * ncf + 0.2 * content + 0.05 * trending`

- Cold-start users: onboarding genre + trending + content blend.
- Warm users: collaborative-heavy weighting.
- Exclude already consumed books.

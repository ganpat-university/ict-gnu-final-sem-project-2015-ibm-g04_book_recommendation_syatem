def blend_scores(
    svd_score: float,
    ncf_score: float,
    content_score: float,
    trending_score: float,
    cold_start: bool = False,
) -> float:
    if cold_start:
        return 0.55 * content_score + 0.35 * trending_score + 0.10 * svd_score
    return 0.40 * svd_score + 0.35 * ncf_score + 0.20 * content_score + 0.05 * trending_score

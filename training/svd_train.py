import argparse
import json
from urllib.parse import urlparse

import numpy as np
import pandas as pd

from data_loader import DataLoader

try:
    import boto3
except ImportError:
    boto3 = None


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Invalid S3 URI: {uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def train_svd(ratings: pd.DataFrame, factors: int = 32):
    user_ids = sorted(ratings["user_id"].astype(int).unique())
    item_ids = sorted(ratings["book_id"].astype(int).unique())
    u_map = {u: i for i, u in enumerate(user_ids)}
    i_map = {it: j for j, it in enumerate(item_ids)}
    mat = np.zeros((len(user_ids), len(item_ids)), dtype=np.float32)
    for _, r in ratings.iterrows():
        mat[u_map[int(r["user_id"])], i_map[int(r["book_id"])]] = float(r["rating"])

    U, s, Vt = np.linalg.svd(mat, full_matrices=False)
    k = min(factors, len(s))
    U_k = U[:, :k] * np.sqrt(s[:k])
    V_k = (Vt[:k, :].T) * np.sqrt(s[:k])
    return U_k, V_k, u_map, i_map


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactions-uri", default="")
    parser.add_argument("--out-s3-uri", required=True)
    parser.add_argument("--factors", type=int, default=32)
    parser.add_argument("--sample-ratings", type=int, default=100000)
    args = parser.parse_args()

    loader = DataLoader()
    if args.interactions_uri:
        interactions = loader.load_interactions(source_uri=args.interactions_uri)
        if interactions is not None and {"user_id", "book_id", "rating"}.issubset(set(interactions.columns)):
            ratings = interactions[["user_id", "book_id", "rating"]].copy()
        else:
            _, _, ratings = loader.load_all(sample_ratings=args.sample_ratings)
    else:
        _, _, ratings = loader.load_all(sample_ratings=args.sample_ratings)

    U_k, V_k, u_map, i_map = train_svd(ratings, factors=args.factors)
    payload = {
        "user_factors": U_k.tolist(),
        "item_factors": V_k.tolist(),
        "user_to_idx": {str(k): v for k, v in u_map.items()},
        "item_to_idx": {str(k): v for k, v in i_map.items()},
        "model_type": "svd",
    }

    if boto3 is None:
        raise RuntimeError("boto3 is required for writing SVD artifacts to S3")
    bucket, key = _parse_s3_uri(args.out_s3_uri)
    boto3.client("s3").put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(payload).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"SVD artifact uploaded to {args.out_s3_uri}")


if __name__ == "__main__":
    main()

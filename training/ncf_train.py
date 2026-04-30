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


def train_ncf(ratings: pd.DataFrame, factors: int = 32, epochs: int = 3, lr: float = 0.01):
    user_ids = sorted(ratings["user_id"].astype(int).unique())
    item_ids = sorted(ratings["book_id"].astype(int).unique())
    u_map = {u: i for i, u in enumerate(user_ids)}
    i_map = {it: j for j, it in enumerate(item_ids)}

    rng = np.random.default_rng(42)
    user_emb = rng.normal(0, 0.1, size=(len(user_ids), factors)).astype(np.float32)
    item_emb = rng.normal(0, 0.1, size=(len(item_ids), factors)).astype(np.float32)
    user_bias = np.zeros(len(user_ids), dtype=np.float32)
    item_bias = np.zeros(len(item_ids), dtype=np.float32)

    rows = ratings[["user_id", "book_id", "rating"]].copy()
    rows["u_idx"] = rows["user_id"].map(u_map).astype(int)
    rows["i_idx"] = rows["book_id"].map(i_map).astype(int)

    for _ in range(epochs):
        rows = rows.sample(frac=1.0, random_state=42)
        for _, r in rows.iterrows():
            u, i, y = int(r["u_idx"]), int(r["i_idx"]), float(r["rating"])
            pred = float(np.dot(user_emb[u], item_emb[i]) + user_bias[u] + item_bias[i])
            err = y - pred
            user_emb[u] += lr * (err * item_emb[i])
            item_emb[i] += lr * (err * user_emb[u])
            user_bias[u] += lr * err
            item_bias[i] += lr * err

    return user_emb, item_emb, user_bias, item_bias, u_map, i_map


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactions-uri", default="")
    parser.add_argument("--out-s3-uri", required=True)
    parser.add_argument("--factors", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=3)
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

    ue, ie, ub, ib, u_map, i_map = train_ncf(
        ratings, factors=args.factors, epochs=args.epochs
    )
    payload = {
        "user_emb": ue.tolist(),
        "item_emb": ie.tolist(),
        "user_bias": ub.tolist(),
        "item_bias": ib.tolist(),
        "user_to_idx": {str(k): v for k, v in u_map.items()},
        "item_to_idx": {str(k): v for k, v in i_map.items()},
        "model_type": "ncf",
    }
    if boto3 is None:
        raise RuntimeError("boto3 is required for writing NCF artifacts to S3")
    bucket, key = _parse_s3_uri(args.out_s3_uri)
    boto3.client("s3").put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(payload).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"NCF artifact uploaded to {args.out_s3_uri}")


if __name__ == "__main__":
    main()

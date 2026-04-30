import json
from io import BytesIO
from urllib.parse import urlparse

import numpy as np
import pandas as pd

try:
    import boto3
except ImportError:
    boto3 = None


class SVDAdapter:
    def __init__(self, artifact_s3_uri: str, books_df: pd.DataFrame):
        self.artifact_s3_uri = artifact_s3_uri
        self.books_df = books_df
        self.user_factors = None
        self.item_factors = None
        self.user_to_idx = {}
        self.item_to_idx = {}
        self.enabled = False
        self._load_artifacts()

    @staticmethod
    def _parse_s3_uri(uri: str) -> tuple[str, str]:
        parsed = urlparse(uri)
        if parsed.scheme != "s3" or not parsed.netloc:
            raise ValueError(f"Invalid S3 URI: {uri}")
        return parsed.netloc, parsed.path.lstrip("/")

    def _load_artifacts(self) -> None:
        if not self.artifact_s3_uri or boto3 is None:
            return
        try:
            bucket, key = self._parse_s3_uri(self.artifact_s3_uri)
            obj = boto3.client("s3").get_object(Bucket=bucket, Key=key)
            payload = json.loads(obj["Body"].read().decode("utf-8"))
            self.user_factors = np.array(payload["user_factors"], dtype=np.float32)
            self.item_factors = np.array(payload["item_factors"], dtype=np.float32)
            self.user_to_idx = {int(k): int(v) for k, v in payload["user_to_idx"].items()}
            self.item_to_idx = {int(k): int(v) for k, v in payload["item_to_idx"].items()}
            self.enabled = True
            print("  ✓ SVDAdapter loaded artifacts from S3")
        except Exception as exc:
            print(f"  [WARN] SVDAdapter artifact load failed: {exc}")

    def get_scores(self, user_id: int, candidate_book_ids: list[int]) -> dict[int, float]:
        if not self.enabled or user_id not in self.user_to_idx:
            return {b: 0.0 for b in candidate_book_ids}
        u = self.user_factors[self.user_to_idx[user_id]]
        scores = {}
        for bid in candidate_book_ids:
            idx = self.item_to_idx.get(int(bid))
            scores[bid] = float(np.dot(u, self.item_factors[idx])) if idx is not None else 0.0
        vals = list(scores.values()) or [0.0]
        lo, hi = min(vals), max(vals)
        if hi > lo:
            scores = {k: (v - lo) / (hi - lo) for k, v in scores.items()}
        return scores

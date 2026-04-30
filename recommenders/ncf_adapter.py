import json
from urllib.parse import urlparse

import numpy as np

try:
    import boto3
except ImportError:
    boto3 = None


class NCFAdapter:
    def __init__(self, artifact_s3_uri: str):
        self.artifact_s3_uri = artifact_s3_uri
        self.user_emb = None
        self.item_emb = None
        self.user_bias = None
        self.item_bias = None
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
            self.user_emb = np.array(payload["user_emb"], dtype=np.float32)
            self.item_emb = np.array(payload["item_emb"], dtype=np.float32)
            self.user_bias = np.array(payload["user_bias"], dtype=np.float32)
            self.item_bias = np.array(payload["item_bias"], dtype=np.float32)
            self.user_to_idx = {int(k): int(v) for k, v in payload["user_to_idx"].items()}
            self.item_to_idx = {int(k): int(v) for k, v in payload["item_to_idx"].items()}
            self.enabled = True
            print("  ✓ NCFAdapter loaded artifacts from S3")
        except Exception as exc:
            print(f"  [WARN] NCFAdapter artifact load failed: {exc}")

    def rerank_scores(self, user_id: int, base_scores: dict[int, float]) -> dict[int, float]:
        if not self.enabled or user_id not in self.user_to_idx:
            return base_scores
        u_idx = self.user_to_idx[user_id]
        u_vec = self.user_emb[u_idx]
        reranked = {}
        for bid, base in base_scores.items():
            i_idx = self.item_to_idx.get(int(bid))
            if i_idx is None:
                reranked[bid] = float(base)
                continue
            ncf_score = float(np.dot(u_vec, self.item_emb[i_idx]) + self.user_bias[u_idx] + self.item_bias[i_idx])
            reranked[bid] = 0.7 * float(base) + 0.3 * ncf_score
        return reranked

import json
import time
from typing import Any
from urllib.parse import urlparse

from config import aws_settings

try:
    import boto3
except ImportError:
    boto3 = None


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Invalid S3 URI: {uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def _write_json_lines_to_s3(records: list[dict[str, Any]], s3_uri: str, suffix: str) -> None:
    if not records or not s3_uri or boto3 is None:
        return
    bucket, key_prefix = _parse_s3_uri(s3_uri)
    key = f"{key_prefix.rstrip('/')}/{int(time.time())}_{suffix}.jsonl"
    body = "\n".join(json.dumps(r) for r in records).encode("utf-8")
    s3 = boto3.client("s3", region_name=aws_settings.AWS_REGION)
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")


def consume_once_to_s3(limit: int = 100) -> int:
    if not aws_settings.ENABLE_KINESIS_EVENTS:
        return 0
    if not aws_settings.KINESIS_STREAM_NAME or boto3 is None:
        return 0

    client = boto3.client("kinesis", region_name=aws_settings.AWS_REGION)
    desc = client.describe_stream_summary(StreamName=aws_settings.KINESIS_STREAM_NAME)
    shard_count = desc["StreamDescriptionSummary"]["OpenShardCount"]
    if shard_count == 0:
        return 0

    shards = client.list_shards(StreamName=aws_settings.KINESIS_STREAM_NAME).get("Shards", [])
    if not shards:
        return 0

    raw_events: list[dict[str, Any]] = []
    for shard in shards:
        shard_id = shard["ShardId"]
        it = client.get_shard_iterator(
            StreamName=aws_settings.KINESIS_STREAM_NAME,
            ShardId=shard_id,
            ShardIteratorType="LATEST",
        )["ShardIterator"]
        resp = client.get_records(ShardIterator=it, Limit=limit)
        for r in resp.get("Records", []):
            try:
                payload = json.loads(r["Data"].decode("utf-8"))
                raw_events.append(payload)
            except Exception:
                continue

    if raw_events:
        _write_json_lines_to_s3(raw_events, aws_settings.KINESIS_S3_RAW_PREFIX, "raw")
        curated = [
            {
                "event_type": e.get("event_type"),
                "event_ts": e.get("event_ts"),
                "user_id": e.get("user_id"),
                "book_id": (e.get("metadata") or {}).get("book_id"),
            }
            for e in raw_events
        ]
        _write_json_lines_to_s3(curated, aws_settings.KINESIS_S3_CURATED_PREFIX, "curated")
    return len(raw_events)


if __name__ == "__main__":
    count = consume_once_to_s3(limit=aws_settings.KINESIS_BATCH_SIZE)
    print(f"Consumed {count} events from Kinesis.")

import json
import time
from typing import Any

from config import aws_settings

try:
    import boto3
except ImportError:
    boto3 = None


class KinesisEventProducer:
    def __init__(self):
        self.enabled = (
            aws_settings.ENABLE_KINESIS_EVENTS
            and bool(aws_settings.KINESIS_STREAM_NAME)
            and boto3 is not None
        )
        self._client = None
        if self.enabled:
            self._client = boto3.client("kinesis", region_name=aws_settings.AWS_REGION)

    def _put(self, payload: dict[str, Any], partition_key: str | None = None) -> bool:
        if not self.enabled or self._client is None:
            return False
        try:
            self._client.put_record(
                StreamName=aws_settings.KINESIS_STREAM_NAME,
                Data=json.dumps(payload).encode("utf-8"),
                PartitionKey=partition_key or aws_settings.KINESIS_PARTITION_KEY,
            )
            return True
        except Exception as exc:
            print(f"[WARN] Kinesis put_record failed: {exc}")
            return False

    def publish_event(self, event_type: str, user_id: Any = None, metadata: dict | None = None) -> bool:
        payload = {
            "event_type": event_type,
            "event_ts": int(time.time()),
            "user_id": user_id,
            "metadata": metadata or {},
        }
        key = str(user_id) if user_id is not None else aws_settings.KINESIS_PARTITION_KEY
        return self._put(payload, partition_key=key)

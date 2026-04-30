import os


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


ENABLE_KINESIS_EVENTS = _env_bool("ENABLE_KINESIS_EVENTS", False)
KINESIS_STREAM_NAME = os.environ.get("KINESIS_STREAM_NAME", "").strip()
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1").strip()
KINESIS_PARTITION_KEY = os.environ.get("KINESIS_PARTITION_KEY", "novelnest").strip()

KINESIS_BATCH_SIZE = int(os.environ.get("KINESIS_BATCH_SIZE", "100"))
KINESIS_S3_RAW_PREFIX = os.environ.get("KINESIS_S3_RAW_PREFIX", "").strip()
KINESIS_S3_CURATED_PREFIX = os.environ.get("KINESIS_S3_CURATED_PREFIX", "").strip()

ENABLE_SAGEMAKER_SVD = _env_bool("ENABLE_SAGEMAKER_SVD", False)
SVD_ARTIFACT_S3_URI = os.environ.get("SVD_ARTIFACT_S3_URI", "").strip()

ENABLE_NCF = _env_bool("ENABLE_NCF", False)
NCF_ARTIFACT_S3_URI = os.environ.get("NCF_ARTIFACT_S3_URI", "").strip()

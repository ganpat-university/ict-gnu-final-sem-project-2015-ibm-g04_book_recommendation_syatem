import os

from aws.kinesis_producer import KinesisEventProducer


def test_kinesis_producer_fallback_disabled():
    os.environ["ENABLE_KINESIS_EVENTS"] = "false"
    producer = KinesisEventProducer()
    assert producer.publish_event("test_event", user_id="u1", metadata={}) is False

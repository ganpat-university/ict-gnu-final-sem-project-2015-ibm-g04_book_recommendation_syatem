import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from aws.kinesis_producer import KinesisEventProducer
from data_loader import DataLoader
from recommenders.hybrid import HybridRecommender


def main():
    print("Smoke: loading sampled datasets...")
    loader = DataLoader()
    books, users, ratings = loader.load_all(sample_ratings=20000)
    assert books is not None and ratings is not None, "Dataset load failed"

    print("Smoke: event producer fallback behavior...")
    producer = KinesisEventProducer()
    ok = producer.publish_event("smoke_event", user_id="smoke-user", metadata={"source": "smoke"})
    if os.environ.get("ENABLE_KINESIS_EVENTS", "").lower() in {"1", "true", "yes", "on"}:
        print(f"  Kinesis publish enabled path returned: {ok}")
    else:
        print("  Kinesis disabled: fallback path OK")

    print("Smoke: hybrid recommender output shape...")
    recommender = HybridRecommender(books, ratings, users, loader=loader)
    uid = int(ratings["user_id"].iloc[0])
    recs = recommender.get_recommendations(user_id=uid, n=10)
    assert recs is not None and not recs.empty, "No recommendations generated"
    assert "book_id" in recs.columns, "Expected book_id column missing"
    print("  Recommendation rows:", len(recs))
    print("Smoke tests passed.")


if __name__ == "__main__":
    main()

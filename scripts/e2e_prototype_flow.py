import argparse
import tempfile
from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from data_loader import DataLoader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-ratings", type=int, default=10000)
    args = parser.parse_args()

    loader = DataLoader()
    books, _, ratings = loader.load_all(sample_ratings=args.sample_ratings)
    assert books is not None and ratings is not None

    interactions = ratings[["user_id", "book_id", "rating"]].copy()
    interactions["event_type"] = "rate"
    interactions["event_ts"] = pd.Timestamp.utcnow().value // 10**9

    tmp = Path(tempfile.gettempdir()) / "novelnest_interactions.csv"
    interactions.to_csv(tmp, index=False)
    print(f"Wrote interactions snapshot: {tmp}")

    # This script intentionally stops before S3 upload/train to keep e2e runnable
    # in local environments without AWS credentials.
    print("E2E prototype data generation complete.")


if __name__ == "__main__":
    main()

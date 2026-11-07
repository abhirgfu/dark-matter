"""Run the queries in sql/ against the NEAR public dataset on BigQuery.

Needs a Google Cloud project and `pip install google-cloud-bigquery`. Nothing else in this repository
depends on it: every chart can be rebuilt without BigQuery.

    python pipeline/run_bigquery.py --project my-project --dry-run
    python pipeline/run_bigquery.py --project my-project --since 2026-08-01 --until 2026-11-06
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys

from common import RAW, ROOT

SQL = ROOT / "sql"
OUT = RAW / "bigquery"
GB = 1024 ** 3


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    yesterday = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    ap.add_argument("--project", required=True)
    ap.add_argument("--since", default="2026-08-01")
    ap.add_argument("--until", default=yesterday.isoformat())
    ap.add_argument("--dry-run", action="store_true", help="print bytes read, run nothing")
    ap.add_argument("--max-gb", type=float, default=200.0, help="refuse any query above this")
    ap.add_argument("--only", help="run one file, for example network_daily")
    args = ap.parse_args()

    try:
        from google.cloud import bigquery
    except ImportError:
        print("Install the client first: pip install google-cloud-bigquery", file=sys.stderr)
        return 2

    client = bigquery.Client(project=args.project)
    params = [
        bigquery.ScalarQueryParameter("since", "STRING", args.since),
        bigquery.ScalarQueryParameter("until", "STRING", args.until),
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    for path in sorted(SQL.glob("*.sql")):
        if args.only and path.stem != args.only:
            continue
        query = path.read_text(encoding="utf-8")
        estimate = client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params, dry_run=True))
        gb = estimate.total_bytes_processed / GB
        print(f"{path.stem}: {gb:,.1f} GB")
        if args.dry_run:
            continue
        if gb > args.max_gb:
            print(f"  skipped: above --max-gb {args.max_gb}")
            continue
        rows = client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
        out = OUT / f"{path.stem}.csv"
        with open(out, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh, lineterminator="\n")
            writer.writerow([f.name for f in rows.schema])
            count = 0
            for row in rows:
                writer.writerow(list(row.values()))
                count += 1
        print(f"  wrote {out.relative_to(ROOT)}: {count} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())

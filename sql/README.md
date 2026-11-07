# BigQuery queries

These run against the NEAR public dataset, `bigquery-public-data.crypto_near_mainnet_us`. Every query
filters on `block_date`, which is the partition column, so it reads only the days it needs.

NEAR pays to store the dataset. You pay normal BigQuery prices for what you read, and the free tier
covers 1 TB a month. Run them with:

```bash
python pipeline/run_bigquery.py --dry-run   # prints the bytes each query would read
python pipeline/run_bigquery.py             # writes data/raw/bigquery/*.csv
```

`run_bigquery.py` needs Google credentials: `gcloud auth application-default login`, or a service
account key in `GOOGLE_APPLICATION_CREDENTIALS`.

| File | What it returns |
|---|---|
| `network_daily.sql` | Daily active signers and transactions for the whole chain |
| `contract_usage_daily.sql` | Daily function calls and distinct contracts called |
| `intents_daily.sql` | Daily transactions and gas burnt on `intents.near` |
| `boundary_daily.sql` | Daily count of transactions touching the treasury |

The dashboard works without these. `pipeline/fetch_market.py` gets the same chain-wide daily metrics
from NearBlocks with no key, so a reader with no Google account can rebuild every chart.

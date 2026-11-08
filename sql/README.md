# BigQuery queries

These run against the NEAR public dataset, `bigquery-public-data.crypto_near_mainnet_us`. Every query
filters on `block_date`, which is the partition column, so it reads only the days it needs.

NEAR pays to store the dataset. You pay normal BigQuery prices for what you read, and the free tier
covers 1 TB a month. A new project runs in the BigQuery sandbox, which needs no card and has the same
free tier.

Create a project at https://console.cloud.google.com/bigquery and note its ID. Then log in, which needs
the [Google Cloud CLI](https://docs.cloud.google.com/sdk/docs/install-sdk), and install the client:

```bash
gcloud auth application-default login
```

```bash
pip install google-cloud-bigquery
```

Run them with:

```bash
python pipeline/run_bigquery.py --project YOUR-PROJECT --dry-run   # prints the data each query would read
```

```bash
python pipeline/run_bigquery.py --project YOUR-PROJECT             # writes data/raw/bigquery/*.csv
```

A query above 200 GB is skipped unless you raise `--max-gb`. `contract_usage_daily` needs about 470 GB from December 2024,
and `boundary_daily` about 2 TB, which is over the free allowance, so run that one on a short date range. Then record the new files and rebuild:

```bash
python pipeline/manifest.py write
```

```bash
python rebuild.py
```

## Tables and a sample query

| Table | Used for |
|---|---|
| `transactions` | Daily active signers and transaction counts, chain-wide and for `intents.near` |
| `receipt_actions` | Contract usage: function calls and distinct contracts called |
| `execution_outcomes` | Logs on `intents.near` that mention the private treasury |

```sql
SELECT
  CAST(block_date AS STRING) AS date,
  COUNT(DISTINCT signer_account_id) AS active_signers,
  COUNT(*) AS transactions
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN @since AND @until
GROUP BY date
ORDER BY date
```

## Queries

| File | What it returns |
|---|---|
| `network_daily.sql` | Daily active signers and transactions for the whole chain |
| `contract_usage_daily.sql` | Daily function calls and distinct contracts called |
| `intents_daily.sql` | Daily transactions and signers on `intents.near` |
| `boundary_daily.sql` | Daily count of log lines on `intents.near` that mention the treasury |
| `top_contracts.sql` | The busiest destinations in four 14-day windows. Its dates are fixed in the file |

The results are kept in `data/raw/bigquery`, so a reader with no Google account can still rebuild every chart. Run with
`--since 2024-12-16 --max-gb 480`, which is what the charts use, and skip `boundary_daily`, which nothing depends on.

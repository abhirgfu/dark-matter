-- Daily receipts on intents.near whose logs mention the private treasury. This is a coarse count of
-- activity at the boundary. Log rows are large, so check the byte estimate with --dry-run first and
-- keep the date range short.
SELECT
  CAST(block_date AS STRING) AS date,
  COUNT(*) AS receipts_touching_treasury
FROM `bigquery-public-data.crypto_near_mainnet_us.execution_outcomes`,
  UNNEST(logs.list) AS log
WHERE block_date BETWEEN @since AND @until
  AND executor_account_id = 'intents.near'
  AND log.element LIKE '%51e8f94d77b5e90dc9852ca6113771e11e8382ce69473a75e313e41665de7cbe%'
GROUP BY date
ORDER BY date

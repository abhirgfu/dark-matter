-- Daily activity on intents.near. Signers here are mostly relayers and solvers: a user signs an
-- intent inside the transaction, so this does not count users.
SELECT
  CAST(block_date AS STRING) AS date,
  COUNT(*) AS transactions,
  COUNT(DISTINCT signer_account_id) AS signers
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN @since AND @until
  AND receiver_account_id = 'intents.near'
GROUP BY date
ORDER BY date

-- Daily active signing accounts and transactions for the whole chain.
SELECT
  CAST(block_date AS STRING) AS date,
  COUNT(DISTINCT signer_account_id) AS active_signers,
  COUNT(*) AS transactions
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN DATE @since AND DATE @until
GROUP BY date
ORDER BY date

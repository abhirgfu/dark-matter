-- Daily function calls and the number of distinct contracts that received one.
SELECT
  CAST(block_date AS STRING) AS date,
  COUNT(*) AS function_calls,
  COUNT(DISTINCT receipt_receiver_account_id) AS active_contracts
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions`
WHERE block_date BETWEEN @since AND @until
  AND action_kind = 'FUNCTION_CALL'
GROUP BY date
ORDER BY date

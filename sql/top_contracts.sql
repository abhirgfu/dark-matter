-- Who the public chain's transactions go to, in four 14-day windows: a year ago, either side of the
-- fall in April 2026, and now. Accounts are grouped by their last two name parts, so the many
-- accounts of one app count as one. The dates are fixed here, so @since and @until do not apply.
SELECT
  CASE
    WHEN block_date BETWEEN DATE '2025-10-24' AND DATE '2025-11-06' THEN '1 a year ago'
    WHEN block_date BETWEEN DATE '2026-03-18' AND DATE '2026-03-31' THEN '2 before the fall'
    WHEN block_date BETWEEN DATE '2026-04-03' AND DATE '2026-04-16' THEN '3 after the fall'
    ELSE '4 now'
  END AS period,
  CASE
    WHEN REGEXP_CONTAINS(receiver_account_id, r'^[0-9a-f]{64}$') THEN '(64-character accounts)'
    WHEN REGEXP_CONTAINS(receiver_account_id, r'^0x[0-9a-f]{40}$') THEN '(0x accounts)'
    ELSE IFNULL(REGEXP_EXTRACT(receiver_account_id, r'([^.]+\.[^.]+)$'), receiver_account_id)
  END AS family,
  COUNT(*) AS transactions,
  COUNT(DISTINCT receiver_account_id) AS accounts,
  COUNT(DISTINCT signer_account_id) AS signers
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN DATE '2025-10-24' AND DATE '2025-11-06'
   OR block_date BETWEEN DATE '2026-03-18' AND DATE '2026-03-31'
   OR block_date BETWEEN DATE '2026-04-03' AND DATE '2026-04-16'
   OR block_date BETWEEN DATE '2026-10-24' AND DATE '2026-11-06'
GROUP BY period, family
QUALIFY ROW_NUMBER() OVER (PARTITION BY period ORDER BY transactions DESC) <= 15
ORDER BY period, transactions DESC

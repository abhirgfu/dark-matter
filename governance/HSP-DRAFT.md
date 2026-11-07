# Draft proposal: private flow transparency

**Status:** discussion draft, not submitted to the House of Stake.
**Evidence:** [THESIS.md](../THESIS.md) and the [method](../docs/METHOD.md).

## Summary

Most of NEAR's revenue now reaches its wallets from the Confidential Intents treasury, and since
27 October most swaps at that boundary settle privately. Nothing public connects revenue to the swaps
that earned it, so nobody outside can tell whether private swaps pay NEAR. This proposal asks for daily
totals that reveal no user's activity, a public account of who controls the treasury, and a stated rule
for how private fees reach NEAR.

It asks for no change to Confidential Intents itself. Individual swaps stay private.

## Why now

NEAR holders are asked to value a token on the revenue of NEAR Intents. Until July 2026 that revenue
could be traced on the public chain from a swap to a wallet. As flow moves to the private chain, the
trail ends at a transfer out of a treasury. Three things follow:

1. Revenue can no longer be checked against activity. A dashboard can show that money arrived, but
   not what earned it.
2. Terms that govern the 1Click API let the private fee be set, changed or removed by Intents
   Technology alone, and describe it as kept for its own account. They also say fees may be directed
   to a recipient for NEAR ecosystem work, and set no amount. How much reaches NEAR is not stated in
   any public document we could find.
3. The treasury holds its balance under one registered key. How that key is held is not public.
4. The private fee is not published. From outside, private swap costs bunch at a few price points well
   above the documented public default. Holders cannot tell how much of that reaches NEAR.

None of this suggests anything is wrong. It means a long-term holder cannot tell, and institutions
that do diligence on NEAR will ask the same questions.

## Proposal

### 1. Publish daily private totals

Each UTC day, publish one signed record per day, with no finer detail:

| Field | Meaning |
|---|---|
| `date` | UTC day |
| `swap_count` | Private swaps settled |
| `volume_usd` | Their total input value |
| `fees_usd` | Total private fees charged |
| `sent_to_near_usd` | The part of those fees sent to NEAR's revenue wallets |
| `shield_usd`, `unshield_usd` | Total into and out of the private chain |
| `treasury_balance_root` | Hash of the private chain's token supply, by token, at day end |

A day total reveals nothing about a user. Days with too few swaps can be merged with the next day, so
that no total can be traced to one person. Anyone can already check `shield_usd` and `unshield_usd`
against public transfers, and the treasury's balance against `intents.near`. That gives every record
a public cross-check.

### 2. Open the totals to one independent check

Selective disclosure is described as planned. When it ships, let an independent auditor use it, or
attest the totals from a trusted execution environment, and publish the result each quarter.

### 3. State who controls the treasury

Publish how the treasury key is held, who can use it, and what happens if it is lost or stolen. Publish
the validator set of the private chain, and how it changes. If the key is held by one signer, move it
to a multisig or threshold scheme, and announce the rotation in advance.

### 4. State the fee rule

Publish the share of the private fee that goes to NEAR's revenue wallets, and any change to it, before
it takes effect. Better still, route it by a contract, so that a change is visible on chain.

## What already exists

These are live or built, and need no permission:

- **Weigh station:** a contract that reads the treasury's balances and keys straight from
  `intents.near`, and warns on chain if a key changes or money leaves fast. See
  [contract/](../contract/README.md).
- **Open data feed:** the daily series behind this proposal, free to use. See the site's data folder.
- **Anchors:** the weigh station can record the hash of each published record, which gives anyone a
  tamper-evident history.

## Cost and risk

The cost is one scheduled report. The main risk is privacy: totals on quiet days could narrow down one
user, which the merge rule above is there to prevent. A second risk is that published fees invite
competition on price. We think holders are owed that number, but this is a fair point to debate.

## Questions for the House of Stake

1. Who should sign the daily record: Intents Technology, the NEAR Foundation, or a set of validators?
2. Should the fee rule be a governance decision, or a disclosure only?
3. What is the right minimum for a daily total?
4. Should the buyback mandate be written into a contract as part of this change?

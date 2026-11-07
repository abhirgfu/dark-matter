# Method

How each number is made, what it depends on, and where it can be wrong. Code paths are relative to the
repository root.

## The idea

Confidential Intents settles swaps on a private fork of NEAR with no public RPC, API or explorer. Tokens
enter it by a transfer to a treasury account on `intents.near`, and leave by a transfer back. The docs
name that account as `PRIVATE_TREASURY_ACCOUNT_ID`:

```text
51e8f94d77b5e90dc9852ca6113771e11e8382ce69473a75e313e41665de7cbe
```

So the private chain has one public edge. Its balance can be read at any block, and every transfer across
it is an ordinary public event. Everything here comes from that edge, from public wallets, and from
public market data.

## Data sources

| Source | Used for | Key needed |
|---|---|---|
| NEAR archival RPC (FastNear, near.org, Tatum) | Treasury balances and keys at past blocks, total supply | No |
| FastNear Transfers API | Transfers in and out of the treasury and wallets | No |
| DefiLlama | Intents volume, fees, revenue; daily token prices | No |
| revenue.near.org | NEAR's daily confidential TVL, embedded in the page | No |
| NearBlocks | Chain-wide daily accounts, transactions, contracts, price | No |
| 1Click token list | Token decimals and symbols once, and live prices for a live reading | No |
| NEAR BigQuery | The same chain-wide metrics, in `sql/` | Google account, optional |
| NEAR Intents Explorer API | Direct swap labels, in `pipeline/fetch_explorer.py` | Partner JWT, optional |

## Weight

`pipeline/fetch_treasury.py` finds a block in the first four minutes of each UTC day and calls
`mt_tokens_for_owner` and `mt_batch_balance_of` on `intents.near` at that block.

`metrics.value_treasury` values each token at DefiLlama's daily price, by CoinGecko id or, failing that,
by contract address. A token with neither stays unpriced and is counted as unpriced. We never guess.

NEAR's series is compared one day back: its value for date D is taken as the end of D, and ours for D+1 is
the start of the next day. The two differ mainly because a few tokens, chiefly QTC, have no public price
history, and because we use daily rather than live prices.

The hero figure and the "Weigh it yourself" button use live prices from the 1Click token list, which
covers more tokens. Those prices are used in the moment and never stored.

## Where revenue comes from

`data/raw/wallet_inflows.json` lists every native NEAR payment into NEAR's three revenue wallets:
`buybacks.multisignature.near`, `fefundsadmin.sputnik-dao.near` and `1csfundsadmin.sputnik-dao.near`.
These are the wallets revenue.near.org names. Their receipts reconcile to DefiLlama's revenue series,
whose method note says it measures NEAR swept into those wallets.

Each payment is a `native_withdraw` intent signed by an account inside `intents.near`. We found by reading
sample transactions that the account paying the wallet is often a fresh one, funded moments earlier by a
transfer out of the treasury of exactly the same amount.

`metrics.match_payments` makes that check for all payments. A payment counts as private when a wNEAR
transfer of exactly the same number of yoctoNEAR left the treasury in the six hours before it. Amounts carry
about 27 significant digits, so a match by chance is not a realistic concern. Each outflow can explain one
payment.

This is a **floor**. A sweep that merges two transfers, or that goes through a second account first, looks
public. "No private trace" means only that the exact match failed.

Treasury outflows of under $400 are not fetched for days before 1 November. Every revenue payment since
April is above $500 (revenue is swept in lumps of about $1,000), so no match is lost. Days before
1 March are not checked: Confidential Intents held almost nothing then, and `data/raw/hand_trace.json`
read 89 payments from January to June and found none from the treasury.

What this shows is the route the money took, not what earned it. A treasury payment could be a private
swap fee, a public fee that was first held in a shielded balance, or anything else. Public data cannot
separate those, which is the point of the finding.

## Flows

`pipeline/fetch_flows.py inflows` pulls transfers into the treasury of at least $2,500 per day. In a full
sample of 9,363 transfers over 2.7 hours, that floor kept about 95% of dollars and about 10% of rows.

Accounts with "solver" in the name are counted apart, because they move inventory rather than swap. Some
unnamed accounts are likely market makers too, so the user figure can only lean high.

## Cost of a private swap

`pipeline/fetch_flows.py windows` pulls every transfer of any size for sampled hours.
`metrics.pair_accounts` finds accounts that are not solvers, with exactly one transfer in and one out inside
the hour. The cost is the share of dollars lost between entry and exit, using the transfer API's own USD
values.

This cost includes the private fee, solver spread and price movement. Accounts that exit to a different
account are missed, so the sample is not all private swaps.

## Revenue per dollar

Wallet receipts divided by DefiLlama volume. It is a blunt ratio: mix, price and the timing of sweeps all
move it. We report windows of weeks, not days.

## What a private dollar earns

`metrics.block_bootstrap_ols` fits daily wallet receipts on public and private dollars, with no intercept,
and draws a 90% interval with a seven-day moving-block bootstrap, because daily revenue is not independent
from day to day. Private dollars are the daily user inflow above; public dollars are reported volume less
that. Sweeps are lumpy and the window is short, so the interval is wide. Read it as a rough range.

## Break-even

`metrics.break_even` finds the daily volume at which revenue pays for each day's new NEAR at today's price:

```text
blended_bps = public_bps * ((1 - private_share) + private_share * capture_ratio)
volume      = new_near_per_day * price / (blended_bps / 10,000)
```

`public_bps` is the earlier level of revenue per dollar. `new_near_per_day` comes from total supply in two
block headers a year apart. The sliders on the site run the same formula in the browser.

## Keys

`pipeline/fetch_control.py` calls `public_keys_of` on `intents.near` at the latest block and at sample dates
back to launch, `view_access_key_list` on the treasury account, and decodes the signed intents in a sample of
transfers out. It also confirms that the registered key is the implicit-account key of the treasury itself.

One registered key does not mean one person. The key could be split across signers. No public document says.

## API terms

The 1ClickSwap API Terms (7 October 2026) do not allow keeping API data for more than 24 hours. So nothing
from the Explorer API and no 1Click quote or price is stored here. The token list is used once for static
facts about each token (symbol, decimals, CoinGecko id), and live prices are used and discarded. This reading
of the terms is ours, not legal advice.

## Reproducing this

```bash
python rebuild.py           # from the raw data here: no network, no keys
python rebuild.py --fresh   # download fresh data first: no keys, but rate-limited
```

`data/manifest.json` holds the SHA-256 of every raw file. `pipeline/verify.py` recalculates the headline
numbers by a second route, with no shared code, and fails if they disagree.

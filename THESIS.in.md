# The thesis: NEAR's best number has gone dark

Research, not financial advice. Every number here is filled in by `python rebuild.py` from raw data in this
repository. Data to {{asof}}. Dataset hash `{{manifest}}`.

## The claim

**NEAR's long-term value now depends on revenue that holders can see arrive but cannot check.**

NEAR's case rests on NEAR Intents earning fees that reach NEAR's wallets. Since {{era_month}}, NEAR has kept about
{{bps_multiple}} times as much of each dollar of volume as it did before, and all of that gain arrived through a
private chain.

This is good news and a new risk together. We expected a leak and found the opposite. But nothing public links those
payments to swaps, one key signs for the treasury, and the private fee is set off-chain. So the next step for NEAR's
value is not only more volume. It is disclosure. Until then, a holder is trusting a report instead of reading a ledger.

The claim has four parts, and each can fail:

1. The private economy is real, and it can be measured from outside.
2. Most of NEAR's revenue now reaches it through the private treasury.
3. NEAR keeps more than it did before.
4. Nobody outside can audit what it keeps or what earned it.

## Evidence for

**The private economy can be weighed.** Every shielded token is backed by one account on `intents.near`. One RPC
call valued it at {{snapshot_usd}} at block {{snapshot_block}}, within {{snapshot_gap}} of the {{reported_usd}} NEAR
reports. Over {{tvl_days}} days, our daily series built from chain balances and public prices tracks NEAR's with a
correlation of {{tvl_corr}} and a median gap of {{tvl_gap}} over the last 60 days. {{near_share}} of the priced value
is NEAR itself: {{near_held}} NEAR, {{near_pct_supply}} of all NEAR in existence.

**Most revenue now comes through it.** We checked {{payments_checked}} payments into NEAR's three revenue wallets
against transfers out of the treasury, to the exact yoctoNEAR. Over the last 30 days at least {{rev_share_recent}} of
revenue dollars left the treasury first. In June it was {{rev_share_june}}. The first such payment came on
{{first_private_text}}, the week Confidential Intents opened to all developers. Reading transactions by hand,
{{trace_treasury}} of {{trace_read}} sampled payments came from the treasury, through {{trace_accounts}} different accounts,
each of which withdrew the same amount to a revenue wallet.

**NEAR keeps more, and all of the gain is private.** In the {{era_baseline_days}} days before {{era_start_text}}, revenue
was {{bps_before}} bps of volume and {{capture_before}} of gross fees. Since then it has been {{bps_after}} bps and
{{capture_after}} of gross fees. The part with no private trace barely moved, from {{bps_public_before}} to {{bps_public}}
bps. The part that left the treasury first went from {{bps_private_before}} to {{bps_private}} bps. This answers the
question we started with. The API terms say a private company keeps the private fee for its own account, so we expected
a leak. We found the opposite.

**Nobody outside can audit it.** The private chain has no public RPC, API or explorer. Wallet receipts match DefiLlama
within {{wallet_gap}}, but DefiLlama's revenue is defined as money swept into those wallets, so that check proves only
that money arrived. Selective disclosure is described as planned, not live.

**Control is narrow and undisclosed.** One key is registered for the treasury, the same at all {{key_dates}} dates we
checked, and it signed {{key_signed}} of {{key_sample}} sampled transfers out. The private fee can be set, changed or
removed by Intents Technology alone, at any time, by route, asset or partner. {{private_part}} of NEAR's take now arrives
by that route.

## Evidence against

- **The route is not the source.** A payment out of the treasury shows where money came from, not what earned it. A new
  partner deal paid through a shielded account would look the same as fees from private swaps. We cannot rule this out
  from public data.
- **Revenue per dollar has spiked before.** It reached {{early_peak_bps}} bps in {{early_peak_week}} with no private trace,
  then fell back. The current level has held for {{bps_after_days}} days, which is not long.
- **The gain may be fading.** Revenue per dollar was {{late_bps_before}} bps in the 30 days to 26 October and
  {{late_bps_after}} bps in the days since. That window is short.
- **Revenue is still small.** It pays for {{coverage_after}} of the value of new NEAR each day. Even if fully audited, NEAR
  would need {{breakeven_today}} of daily volume, {{breakeven_multiple}} times today's {{volume_day}}, to pay for new NEAR
  at today's price and issuance. Disclosure does not fix that.
- **One key may not mean one person.** The key could be split across signers. We can only say that nobody outside can tell.
- **Markets may not care.** NEAR's price has risen a lot this year with none of this disclosed. Opacity may never be
  priced, or a planned feature may fix it first.
- **The private economy is not growing in a straight line.** The treasury is below its September peak, and much of the
  flow belongs to solvers moving inventory rather than to users.

## What would change our mind

Each test is computed on every rebuild, or checked by hand where it depends on a public statement. The rules are in
`pipeline/falsifiers.py`.

{{test_table}}

We would drop the thesis if NEAR or Intents Technology published private totals that an auditor could check, or if the
share of revenue from the treasury fell back below a quarter. We would become more worried if revenue per dollar fell back
to its old level while private flow held up, because that would mean private flow had stopped paying NEAR.

## What could not be computed

- The private fee. No public source gives its rate. Dry quotes for confidential swaps need a partner login.
- Private swap volume. We see money cross the boundary, not swaps inside.
- Who solves private swaps. Solver identity stays on the private chain.
- How the treasury key is held.
- What earned any single revenue payment.
- The value of {{unpriced_tokens}} of the treasury's {{all_tokens}} tokens on past dates, because they have no public price
  history.

## What it means

The private path looks like the most valuable thing NEAR Intents has shipped this year, and the least visible. The
long-term case now rests on three things:

1. Private flow keeps growing.
2. NEAR's share of it holds, without a rule that requires it to.
3. Holders get a way to check it.

The first two are bets. The third is a choice, and a cheap one. A daily total reveals nobody's trades.
[The draft proposal](governance/HSP-DRAFT.md) sets out how, and the [weigh station](contract/README.md) already works
without anyone's permission.

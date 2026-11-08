# The thesis: NEAR's long-term value now rests on revenue nobody outside can check

Research, not financial advice. **Horizon: five years, to 2031, reviewed every 12 months.** Every number here is filled in
by `python rebuild.py` from raw data in this repository. Data to {{asof}}. Dataset hash `{{manifest}}`.

## The claim

**NEAR is turning from a chain people use directly into a settlement layer for cross-chain money, more and more of it
private. Over the next five years its value depends on getting paid for that flow, and on holders being able to check
that it does.**

In a year, NEAR Intents volume rose about {{volume_year}} times while active accounts fell {{accounts_year}}. At its recent
pace, volume could make NEAR's revenue pay for all new NEAR by 2031. But {{private_part}} of what NEAR keeps now arrives
through a private chain, nothing public links that money to any swap, one key signs for the treasury, and the private fee
is set off-chain. Since swaps themselves moved to that chain on 27 October, the take has slipped.

So the next step for NEAR's value is not only more volume. It is proof that the volume pays. Until then, a holder is
trusting a report instead of reading a ledger.

The claim has six parts, and each can fail:

1. The main use of NEAR is shifting from public accounts to cross-chain settlement.
2. Volume is growing fast enough to matter by 2031.
3. The private economy is real, and it can be measured from outside.
4. Most of NEAR's revenue now arrives through the private treasury, and all of the recent gain came that way.
5. Whether private swaps pay NEAR is an open test, running now.
6. Nobody outside can audit what NEAR keeps or what earned it.

## The five-year case

NEAR issues about {{issued_day}} new NEAR a day, worth {{model_usd_day}} at ${{model_price}}. Revenue of {{rev_late_day}} a day
pays for {{coverage_after}} of that. NEAR's market cap of {{market_cap}} is {{multiple_now}} times its yearly revenue of
{{revenue_year}}, so today's price already assumes a lot of growth.

For revenue to pay for all new NEAR by 2031, at today's price and take, volume must grow {{needed_floor}} a year at the 1.6%
issuance floor in HSP-029, or {{needed_cap}} a year at the 2.5% cap. The 12-month trend is {{observed_growth}}. If private swaps
pay NEAR nothing, the need rises to {{needed_public}} a year. **So the volume is on pace, and the take is the question.**

| Case in 2031 | What it assumes | Volume a year | Take | Revenue | New NEAR paid for | Market cap to revenue |
|---|---|---|---|---|---|---|
| Stalls | Volume stops growing, private swaps pay NEAR nothing, issuance stays at 2.5% | {{growth_stalls}} | {{take_stalls}} bps | {{rev_stalls}} | {{cover_stalls}} | {{mult_stalls}}× |
| Holds | Volume grows at half its recent pace, the take stays, HSP-029 lands | {{growth_holds}} | {{take_holds}} bps | {{rev_holds}} | {{cover_holds}} | {{mult_holds}}× |
| Private layer wins | Volume keeps its recent pace, the take recovers, HSP-029 lands | {{growth_wins}} | {{take_wins}} bps | {{rev_wins}} | {{cover_wins}} | {{mult_wins}}× |

These are arithmetic on stated assumptions, not forecasts. They hold NEAR's price and market cap at today's level. A higher
price makes new NEAR worth more, so revenue would pay for less of it.

**Yearly checkpoints.** The thesis is on track only if these hold each November:

| By | Revenue pays for | Also needed |
|---|---|---|
| 2027 | At least 25% of new NEAR | Private totals published, and the treasury's custody explained |
| 2029 | At least 50% of new NEAR | A public rule for how private fees reach NEAR |
| 2031 | All new NEAR, or close to it | |

## Evidence for

**The private economy can be weighed.** Every shielded token is backed by one account on `intents.near`. One RPC
call valued it at {{snapshot_usd}} at block {{snapshot_block}}, within {{snapshot_gap}} of the {{reported_usd}} NEAR
reports. Over {{tvl_days}} days, our daily series built from chain balances and public prices tracks NEAR's with a
correlation of {{tvl_corr}} and a median gap of {{tvl_gap_all}}, or {{tvl_gap}} over the last 60 days, when tokens with no
public price history grew. {{near_share}} of the priced value
is NEAR itself: {{near_held}} NEAR, {{near_pct_supply}} of all NEAR in existence.

**Most revenue now comes through it.** We checked {{payments_checked}} payments into NEAR's three revenue wallets
against transfers out of the treasury, to the exact yoctoNEAR. Over the last 30 days at least {{rev_share_recent}} of
revenue dollars left the treasury first. In June it was {{rev_share_june}}. The first such payment came on
{{first_private_text}}, the week Confidential Intents opened to all developers. Reading transactions by hand,
{{trace_treasury}} of {{trace_read}} sampled payments came from the treasury, through {{trace_accounts}} different accounts,
each of which withdrew the same amount to a revenue wallet.

**NEAR kept more, and all of the gain was private.** In the {{era_baseline_days}} days before {{era_start_text}}, revenue
was {{bps_before}} bps of volume and {{capture_before}} of gross fees. Since then it has been {{bps_after}} bps and
{{capture_after}} of gross fees. The part with no private trace barely moved, from {{bps_public_before}} to {{bps_public}}
bps. The part that left the treasury first went from {{bps_private_before}} to {{bps_private}} bps.

**Then the swaps moved, and the take slipped.** In {{swap_hours_before}} sampled hours before 27 October we saw about
{{swaps_before}} private swaps an hour at the boundary. In {{swap_hours_after}} hours since, about {{swaps_after}}. Money
entering the treasury from accounts other than solvers went from {{flow_share_before}} of reported volume to
{{flow_share_recent}}. So the gain above did not come from swaps that enter and leave in one go, which were few. It may have come from swaps made
inside shielded balances, a partner deal, or public fees held in shielded form. And when swaps did move in bulk, revenue
per dollar did not rise with them. It fell {{late_fall}}, with the public part going from
{{late_public_before}} to {{late_public_after}} bps and the private part from {{late_private_before}} to
{{late_private_after}} bps. The API terms say a private company keeps the private fee for its own account, so this is
the leak we set out to look for. {{late_days}} days is too few to call it. {{fit_sentence}}

**The private fee leaves a fingerprint.** Across {{fee_swaps}} private swaps between different assets since 27 October, the
cost from entry to exit does not spread smoothly. It bunches near {{fee_base}}, {{fee_low}} and {{fee_high}} bps. That looks
like a price list, and no public document gives one. The documented public default is 20 bps. At the sampled rate, private swappers lose about {{lost_day}} a day between entry and exit, against
{{rev_late_day}} a day reaching NEAR's wallets from every source. Part of that gap is solver spread and price movement.

**Nobody outside can audit it.** The private chain has no public RPC, API or explorer. Even the partner Explorer API, which
has a field for confidential swaps, labelled {{explorer_private}} of {{explorer_swaps}} swaps that way. Wallet receipts match
DefiLlama within {{wallet_gap}}, but DefiLlama's revenue is defined as money swept into those wallets, so that check proves
only that money arrived. Selective disclosure is described as planned, not live.

**Control is narrow and undisclosed.** One key is registered for the treasury, the same at all {{key_dates}} dates we
checked, and it signed {{key_signed}} of {{key_sample}} sampled transfers out. The private fee can be set, changed or
removed by Intents Technology alone, at any time, by route, asset or partner. The terms say fees may be directed to a
recipient for NEAR ecosystem work, and set no amount. {{private_part}} of NEAR's take now arrives by this route.

**The chain's own records show the shift.** Over the last 90 days `intents.near` took {{intents_share_now}} of all NEAR
transactions, up from {{intents_share_then}} a year ago, and {{intents_share_recent}} in the last 14 days. It went from the
{{rank_then}} busiest destination on the chain to the {{rank_now}}. Its transactions rose {{intents_year}} over the year, while
the chain's total fell {{txns_year}}.

## Evidence against

- **The route is not the source.** A payment out of the treasury shows where money came from, not what earned it. A new
  partner deal paid through a shielded account would look the same as fees from private swaps. We cannot rule this out
  from public data.
- **Public usage did not move to Intents.** Most of the fall in transactions was one sender stopping, as set out below.
  `intents.near` gained about {{intents_gain}} transactions a day over the year, while the chain lost about {{chain_loss}}. So
  its rising share comes mostly from the rest shrinking. Active accounts count a bot only once, and they still fell
  {{accounts_year}}, so real users left too. We do not know where they went.
- **Volume does not lead chain usage.** The track's hypothesis is not supported, as set out below.
- **Reported volume is not all 1Click.** The Explorer's 1Click swaps come to {{explorer_share}} of DefiLlama's volume. The
  rest runs through routes we cannot check, and every bps figure here divides by DefiLlama's number.
- **The growth trend is noisy.** Monthly volume has swung widely, so a {{observed_growth}} yearly trend could easily change.
  We did not test whether NEAR Intents is keeping its share against rival cross-chain routes.
- **Revenue per dollar has spiked before.** It reached {{early_peak_bps}} bps in {{early_peak_week}} with no private trace,
  then fell back. The current level has held for {{bps_after_days}} days, which is not long.
- **The gain may be fading.** Revenue per dollar was {{late_bps_before}} bps in the 30 days to 26 October and
  {{late_bps_after}} bps in the days since. That window is short.
- **The slip may be nothing.** {{late_days}} days is short. Sweeps are lumpy, volume mix moves, and fees collected on the
  private chain may simply reach the wallets later.
- **Revenue is still small.** It pays for {{coverage_after}} of the value of new NEAR each day. Even if fully audited, NEAR
  would need {{breakeven_today}} of daily volume, {{breakeven_multiple}} times today's {{volume_day}}, to pay for new NEAR
  at today's price and issuance. Disclosure does not fix that.
- **One key may not mean one person.** The key could be split across signers. We can only say that nobody outside can tell.
- **Markets may not care.** NEAR's price has risen a lot this year with none of this disclosed. Opacity may never be
  priced, or a planned feature may fix it first.
- **The private economy is not growing in a straight line.** The treasury is below its September peak, and much of the
  flow belongs to solvers moving inventory rather than to users.

## The track's hypothesis

The track's sample prompt asks whether cross-chain volume through NEAR Intents is a better leading indicator of real
network usage than token price. **Result: {{h_verdict}}.**

We compared the last four weeks of change in volume, and in price, with the next four weeks of change in usage, over
{{h_weeks}} weeks. Rank correlation is used so that one extreme week cannot decide it.

| Usage measure | Volume | Price |
|---|---|---|
| Active accounts | {{h_accounts_v}} | {{h_accounts_p}} |
| Transactions | {{h_txns_v}} | {{h_txns_p}} |
| Function calls | {{h_calls_v}} | {{h_calls_p}} |

The links are weak. {{h_gap}} So the data does not show that volume is the better indicator. It does not show that price
is, either.

The prompt asks for swap volume from the Explorer API, but its terms bar keeping the data, and its records start later, so
the test above uses DefiLlama's volume. {{explorer_test}}

This cuts against the idea as stated. Over the last year volume rose about {{volume_year}} times while active accounts fell
{{accounts_year}}, transactions {{txns_year}} and function calls {{calls_year}}. BigQuery shows why the two came apart: most
of the fall has nothing to do with Intents. Until the start of April 2026, at most {{sender_signers}} signing accounts sent
about {{sender_per_day}} transactions a day to `wallet.kaiching` and {{sender_accounts}} `*.users.kaiching` accounts. That was
{{sender_share}} of the chain's transactions. When it stopped, it made up {{sender_fall_share}} of that month's fall, and {{sender_year_share}} of the
fall over the year. We do not know why it stopped.

So chain-wide transaction counts were mostly measuring a few automated senders, and volume could not have predicted them.
Volume measures the settlement business. It does not predict the old one.

## What would change our mind

Each test is computed on every rebuild, or checked by hand where it depends on a public statement. The rules are in
`pipeline/falsifiers.py`.

{{test_table}}

**The live test.** If private swaps pay NEAR, revenue per dollar holds near {{late_bps_before}} bps as they grow. If they do
not, it falls toward the part with no private trace, about {{public_floor}} bps. The latest {{last_week_days}} days: {{last_week_bps}} bps.

We would drop the thesis if NEAR or Intents Technology published private totals that an auditor could check, or if the
share of revenue from the treasury fell back below a quarter.

## What could not be computed

- Function calls after {{bq_last}}. BigQuery needs a Google login, so the daily refresh cannot run it. Accounts and
  transactions carry on from NearBlocks, which matched BigQuery on {{agree_accounts}} and {{agree_txns}} of {{agree_days}}
  days.
- `sql/boundary_daily.sql`. It reads more than the free monthly allowance and no chart needs it, so it has not been run.
- Private swaps in the Explorer API. We ran `pipeline/fetch_explorer.py` on {{explorer_checked}} with a partner key. Over
  {{explorer_days}} full days it showed {{explorer_swaps}} swaps, worth {{explorer_share}} of DefiLlama's volume, because it
  covers 1Click swaps only. {{explorer_private}} of them were labelled confidential, although we saw about {{swaps_after}}
  private swaps an hour at the boundary. So this API does not show the private economy either. Its terms bar keeping the data
  for more than 24 hours, so the daily files are deleted and only this summary is kept. Volume elsewhere comes from DefiLlama.
- NEAR Intents' market share against rival routes.
- The private fee itself. No public source gives its rate, and dry quotes for confidential swaps need a partner login. We
  can only see the total lost between entry and exit, which also holds solver spread and price movement.
- Private swap volume. We see money cross the boundary, not swaps inside.
- Who solves private swaps. Solver identity stays on the private chain.
- How the treasury key is held.
- What earned any single revenue payment.
- The value of {{unpriced_tokens}} of the treasury's {{all_tokens}} tokens on past dates, because they have no public price
  history.

## What it means

Private settlement may be the most valuable thing NEAR Intents has shipped this year, and it is the least visible. Over
five years, the long-term case rests on three things:

1. Volume keeps growing at {{needed_floor}} to {{needed_cap}} a year.
2. NEAR gets paid for it, without a public rule that says it must.
3. Holders get a way to check.

The first two are bets. The third is a choice, and a cheap one. A daily total reveals nobody's trades.
[The draft proposal](governance/HSP-DRAFT.md) sets out how, and the [weigh station](contract/README.md) is ready to deploy.

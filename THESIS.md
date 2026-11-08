# The thesis: NEAR's long-term value now rests on revenue nobody outside can check

Research, not financial advice. **Horizon: five years, to 2031, reviewed every 12 months.** Every number here is filled in
by `python rebuild.py` from raw data in this repository. Data to 2026-11-07. Dataset hash `5a3f5c66fa57450a64e6e746bec621b8a90df2065aec1b733d2c514333803c92`.

## The claim

**NEAR is turning from a chain people use directly into a settlement layer for cross-chain money, more and more of it
private. Over the next five years its value depends on getting paid for that flow, and on holders being able to check
that it does.**

In a year, NEAR Intents volume rose about 3.7 times while active accounts fell 76%. At its recent
pace, volume could make NEAR's revenue pay for all new NEAR by 2031. But 72% of what NEAR keeps now arrives
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

NEAR issues about 86,913 new NEAR a day, worth $317.9K at $3.66. Revenue of $60.2K a day
pays for 19% of that. NEAR's market cap of $4.8B is 218 times its yearly revenue of
$22.0M, so today's price already assumes a lot of growth.

For revenue to pay for all new NEAR by 2031, at today's price and take, volume must grow +30% a year at the 1.6%
issuance floor in HSP-029, or +44% a year at the 2.5% cap. The 12-month trend is +46%. If private swaps
pay NEAR nothing, the need rises to +69% a year. **So the volume is on pace, and the take is the question.**

| Case in 2031 | What it assumes | Volume a year | Take | Revenue | New NEAR paid for | Market cap to revenue |
|---|---|---|---|---|---|---|
| Stalls | Volume stops growing, private swaps pay NEAR nothing, issuance stays at 2.5% | +0% | 1.26 bps | $6.1M | 4% | 793× |
| Holds | Volume grows at half its recent pace, the take stays, HSP-029 lands | +23% | 4.56 bps | $61.4M | 73% | 78× |
| Private layer wins | Volume keeps its recent pace, the take recovers, HSP-029 lands | +46% | 5.32 bps | $168.0M | 200% | 29× |

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
call valued it at $140.3M at block 223,490,355, within 1.1% of the $141.9M NEAR
reports. Over 246 days, our daily series built from chain balances and public prices tracks NEAR's with a
correlation of 0.997 and a median gap of 1.1%, or 5.1% over the last 60 days, when tokens with no
public price history grew. 35% of the priced value
is NEAR itself: 12.5M NEAR, 1.0% of all NEAR in existence.

**Most revenue now comes through it.** We checked 5,083 payments into NEAR's three revenue wallets
against transfers out of the treasury, to the exact yoctoNEAR. Over the last 30 days at least 72% of
revenue dollars left the treasury first. In June it was 0%. The first such payment came on
7 July, the week Confidential Intents opened to all developers. Reading transactions by hand,
33 of 163 sampled payments came from the treasury, through 33 different accounts,
each of which withdrew the same amount to a revenue wallet.

**NEAR kept more, and all of the gain was private.** In the 60 days before 21 September, revenue
was 2.83 bps of volume and 20% of gross fees. Since then it has been 5.06 bps and
32% of gross fees. The part with no private trace barely moved, from 1.45 to 1.39
bps. The part that left the treasury first went from 1.38 to 3.67 bps.

**Then the swaps moved, and the take slipped.** In 3 sampled hours before 27 October we saw about
18 private swaps an hour at the boundary. In 7.7 hours since, about 519. Money
entering the treasury from accounts other than solvers went from 15% of reported volume to
42%. So the gain above did not come from swaps that enter and leave in one go, which were few. It may have come from swaps made
inside shielded balances, a partner deal, or public fees held in shielded form. And when swaps did move in bulk, revenue
per dollar did not rise with them. It fell 14%, with the public part going from
1.52 to 1.26 bps and the private part from 3.81 to
3.30 bps. The API terms say a private company keeps the private fee for its own account, so this is
the leak we set out to look for. 11 days is too few to call it. A rough fit over 26 days puts a dollar crossing the boundary at about 2.8 bps to NEAR and any other dollar at about 5.5 bps. The 90% interval on the private figure runs from 0 to 14 bps, so it cannot settle the question yet.

**The private fee leaves a fingerprint.** Across 1,594 private swaps between different assets since 27 October, the
cost from entry to exit does not spread smoothly. It bunches near 19, 77 and 146 bps. That looks
like a price list, and no public document gives one. The documented public default is 20 bps. At the sampled rate, private swappers lose about $223.1K a day between entry and exit, against
$60.2K a day reaching NEAR's wallets from every source. Part of that gap is solver spread and price movement.

**Nobody outside can audit it.** The private chain has no public RPC, API or explorer. Even the partner Explorer API, which
has a field for confidential swaps, labelled 0 of 230,251 swaps that way. Wallet receipts match
DefiLlama within 1.0%, but DefiLlama's revenue is defined as money swept into those wallets, so that check proves
only that money arrived. Selective disclosure is described as planned, not live.

**Control is narrow and undisclosed.** One key is registered for the treasury, the same at all 10 dates we
checked, and it signed 24 of 24 sampled transfers out. The private fee can be set, changed or
removed by Intents Technology alone, at any time, by route, asset or partner. The terms say fees may be directed to a
recipient for NEAR ecosystem work, and set no amount. 72% of NEAR's take now arrives by this route.

**The chain's own records show the shift.** Over the last 90 days `intents.near` took 9.3% of all NEAR
transactions, up from 1.0% a year ago, and 15.8% in the last 14 days. It went from the
fifth busiest destination on the chain to the first. Its transactions rose 53% over the year, while
the chain's total fell 84%.

## Evidence against

- **The route is not the source.** A payment out of the treasury shows where money came from, not what earned it. A new
  partner deal paid through a shielded account would look the same as fees from private swaps. We cannot rule this out
  from public data.
- **Public usage did not move to Intents.** Most of the fall in transactions was one sender stopping, as set out below.
  `intents.near` gained about 23,925 transactions a day over the year, while the chain lost about 3.9M. So
  its rising share comes mostly from the rest shrinking. Active accounts count a bot only once, and they still fell
  76%, so real users left too. We do not know where they went.
- **Volume does not lead chain usage.** The track's hypothesis is not supported, as set out below.
- **Reported volume is not all 1Click.** The Explorer's 1Click swaps come to 29% of DefiLlama's volume. The
  rest runs through routes we cannot check, and every bps figure here divides by DefiLlama's number.
- **The growth trend is noisy.** Monthly volume has swung widely, so a +46% yearly trend could easily change.
  We did not test whether NEAR Intents is keeping its share against rival cross-chain routes.
- **Revenue per dollar has spiked before.** It reached 4.2 bps in June with no private trace,
  then fell back. The current level has held for 47 days, which is not long.
- **The gain may be fading.** Revenue per dollar was 5.32 bps in the 30 days to 26 October and
  4.56 bps in the days since. That window is short.
- **The slip may be nothing.** 11 days is short. Sweeps are lumpy, volume mix moves, and fees collected on the
  private chain may simply reach the wallets later.
- **Revenue is still small.** It pays for 19% of the value of new NEAR each day. Even if fully audited, NEAR
  would need $697.3M of daily volume, 5.3 times today's $132.0M, to pay for new NEAR
  at today's price and issuance. Disclosure does not fix that.
- **One key may not mean one person.** The key could be split across signers. We can only say that nobody outside can tell.
- **Markets may not care.** NEAR's price has risen a lot this year with none of this disclosed. Opacity may never be
  priced, or a planned feature may fix it first.
- **The private economy is not growing in a straight line.** The treasury is below its September peak, and much of the
  flow belongs to solvers moving inventory rather than to users.

## The track's hypothesis

The track's sample prompt asks whether cross-chain volume through NEAR Intents is a better leading indicator of real
network usage than token price. **Result: Not supported.**

We compared the last four weeks of change in volume, and in price, with the next four weeks of change in usage, over
98 weeks. Rank correlation is used so that one extreme week cannot decide it.

| Usage measure | Volume | Price |
|---|---|---|
| Active accounts | 0.18 | 0.29 |
| Transactions | 0.04 | -0.09 |
| Function calls | 0.01 | -0.08 |

The links are weak. For all three measures the 90% interval on the gap includes zero. So the data does not show that volume is the better indicator. It does not show that price
is, either.

The prompt asks for swap volume from the Explorer API, but its terms bar keeping the data, and its records start later, so
the test above uses DefiLlama's volume. We ran the same test on the Explorer's own volume: swaps of at least $2,500, which carry 90% of its dollars, over 73 weeks from 2025-06-09, when its records begin. The result is not supported, the same as with DefiLlama's volume. For active accounts the rank correlation is 0.33 for volume against 0.43 for price.

This cuts against the idea as stated. Over the last year volume rose about 3.7 times while active accounts fell
76%, transactions 84% and function calls 80%. BigQuery shows why the two came apart: most
of the fall has nothing to do with Intents. Until the start of April 2026, at most 3 signing accounts sent
about 2.3M transactions a day to `wallet.kaiching` and 27M `*.users.kaiching` accounts. That was
62% of the chain's transactions. When it stopped, it made up 83% of that month's fall, and 64% of the
fall over the year. We do not know why it stopped.

So chain-wide transaction counts were mostly measuring a few automated senders, and volume could not have predicted them.
Volume measures the settlement business. It does not predict the old one.

## What would change our mind

Each test is computed on every rebuild, or checked by hand where it depends on a public statement. The rules are in
`pipeline/falsifiers.py`.

| Test | Breaks if | Now | State |
|---|---|---|---|
| The treasury can be weighed from the public chain | Our figure sits more than 15% from NEAR's on a typical day in the last 60 | 5.1% median gap | Holding |
| Most of NEAR's revenue comes through the private treasury | Under 25% of the last 30 days' revenue left the treasury first | 72% in the last 30 days | Holding |
| NEAR keeps more than it did before | Revenue per dollar falls back to its level before the step | 1.8× the earlier level | Holding |
| Private swaps pay NEAR as public swaps did | Since 27 October, revenue per dollar falls below 60% of the 30 days before | 86% of the earlier level | Watch |
| Volume grows fast enough to pay for new NEAR by 2031 | The 12-month volume trend falls below the 30% a year that needs | +46% a year | Holding |
| Revenue pays for more of the new NEAR each year | At the November 2027 review, revenue pays for under 25% of new NEAR | 19% today | Due Nov 2027 |
| The private economy holds its size | The treasury falls more than 60% from its peak | 70% of peak | Holding |
| One key signs for the treasury | More than one key is registered, or the custody setup is published | 1 key | Holding |
| Private totals cannot be audited from outside | NEAR or Intents Technology publishes private volume and fees that an auditor can check | none found, checked 2026-11-07 | Holding |

**The live test.** If private swaps pay NEAR, revenue per dollar holds near 5.32 bps as they grow. If they do
not, it falls toward the part with no private trace, about 1.26 bps. The latest 5 days: 3.92 bps.

We would drop the thesis if NEAR or Intents Technology published private totals that an auditor could check, or if the
share of revenue from the treasury fell back below a quarter.

## What could not be computed

- Function calls after 2026-11-06. BigQuery needs a Google login, so the daily refresh cannot run it. Accounts and
  transactions carry on from NearBlocks, which matched BigQuery on 691 and 689 of 691
  days.
- `sql/boundary_daily.sql`. It reads more than the free monthly allowance and no chart needs it, so it has not been run.
- Private swaps in the Explorer API. We ran `pipeline/fetch_explorer.py` on 2026-11-07 with a partner key. Over
  13 full days it showed 230,251 swaps, worth 29% of DefiLlama's volume, because it
  covers 1Click swaps only. 0 of them were labelled confidential, although we saw about 519
  private swaps an hour at the boundary. So this API does not show the private economy either. Its terms bar keeping the data
  for more than 24 hours, so the daily files are deleted and only this summary is kept. Volume elsewhere comes from DefiLlama.
- NEAR Intents' market share against rival routes.
- The private fee itself. No public source gives its rate, and dry quotes for confidential swaps need a partner login. We
  can only see the total lost between entry and exit, which also holds solver spread and price movement.
- Private swap volume. We see money cross the boundary, not swaps inside.
- Who solves private swaps. Solver identity stays on the private chain.
- How the treasury key is held.
- What earned any single revenue payment.
- The value of 33 of the treasury's 193 tokens on past dates, because they have no public price
  history.

## What it means

Private settlement may be the most valuable thing NEAR Intents has shipped this year, and it is the least visible. Over
five years, the long-term case rests on three things:

1. Volume keeps growing at +30% to +44% a year.
2. NEAR gets paid for it, without a public rule that says it must.
3. Holders get a way to check.

The first two are bets. The third is a choice, and a cheap one. A daily total reveals nobody's trades.
[The draft proposal](governance/HSP-DRAFT.md) sets out how, and the [weigh station](contract/README.md) is ready to deploy.

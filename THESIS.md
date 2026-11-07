# The thesis: NEAR's most important number has gone dark

Research, not financial advice. Every number here is filled in by `python rebuild.py` from raw data in this
repository. Data to 2026-11-07. Dataset hash `e9ae12cefa768cba4b88ea2d6357817aebc287af796b6ae6c6ae35994c16d046`.

## The claim

**NEAR's long-term value now depends on revenue that holders can see arrive but cannot check, and the next weeks will
show whether private swaps pay NEAR at all.**

NEAR's case rests on NEAR Intents earning fees that reach NEAR's wallets. From September, NEAR kept about
1.8 times as much of each dollar of volume as before, and all of that gain arrived through a private chain.
On 27 October swaps themselves moved there: about 29 times as many now cross the boundary. Since then the
take has slipped, from 5.32 to 4.56 bps.

Nothing public links NEAR's revenue to any swap, one key signs for the treasury, and the private fee is set off-chain.
So the next step for NEAR's value is not only more volume. It is disclosure. Until then, a holder is trusting a report
instead of reading a ledger.

The claim has five parts, and each can fail:

1. The private economy is real, and it can be measured from outside.
2. Most of NEAR's revenue now reaches it through the private treasury.
3. NEAR kept more from that route, before swaps themselves moved.
4. Whether private swaps pay NEAR is an open test, running now.
5. Nobody outside can audit what NEAR keeps or what earned it.

## Evidence for

**The private economy can be weighed.** Every shielded token is backed by one account on `intents.near`. One RPC
call valued it at $141.3M at block 223,474,482, within 0.4% of the $141.9M NEAR
reports. Over 246 days, our daily series built from chain balances and public prices tracks NEAR's with a
correlation of 0.997 and a median gap of 5.1% over the last 60 days. 35% of the priced value
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
18 private swaps an hour at the boundary. In 7.7 hours since, about 519. So the
gain above cannot have come from swaps crossing the boundary, which were few. It must have come from something else:
swaps inside shielded balances, a partner deal, or public fees held in shielded form. And when swaps did move in bulk,
revenue per dollar did not rise with them. It fell −14%, with the public part going from
1.52 to 1.26 bps and the private part from 3.81 to
3.30 bps. The API terms say a private company keeps the private fee for its own account, so this is
the leak we set out to look for. 11 days is too few to call it.

**The private fee leaves a fingerprint.** Across 1,594 private swaps between different assets since 27 October, the
cost from entry to exit does not spread smoothly. It bunches near 19, 77 and 146 bps. That looks
like a price list, and no public document gives one. The documented public default is 20 bps. At the sampled rate, private swappers lose about $223.1K a day between entry and exit, against
$60.2K a day reaching NEAR's wallets from every source. Part of that gap is solver spread and price movement.

**Nobody outside can audit it.** The private chain has no public RPC, API or explorer. Wallet receipts match DefiLlama
within 1.0%, but DefiLlama's revenue is defined as money swept into those wallets, so that check proves only
that money arrived. Selective disclosure is described as planned, not live.

**Control is narrow and undisclosed.** One key is registered for the treasury, the same at all 10 dates we
checked, and it signed 24 of 24 sampled transfers out. The private fee can be set, changed or
removed by Intents Technology alone, at any time, by route, asset or partner. The terms say fees may be directed to a
recipient for NEAR ecosystem work, and set no amount. 72% of NEAR's take now arrives by this route.

## Evidence against

- **The route is not the source.** A payment out of the treasury shows where money came from, not what earned it. A new
  partner deal paid through a shielded account would look the same as fees from private swaps. We cannot rule this out
  from public data.
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

## What would change our mind

Each test is computed on every rebuild, or checked by hand where it depends on a public statement. The rules are in
`pipeline/falsifiers.py`.

| Test | Breaks if | Now | State |
|---|---|---|---|
| The treasury can be weighed from the public chain | Our figure sits more than 15% from NEAR's on a typical day in the last 60 | 5.1% median gap | Holding |
| Most of NEAR's revenue comes through the private treasury | Under 25% of the last 30 days' revenue left the treasury first | 72% in the last 30 days | Holding |
| NEAR keeps more than it did before | Revenue per dollar falls back to its level before the step | 1.8× the earlier level | Holding |
| Private swaps pay NEAR as public swaps did | Since 27 October, revenue per dollar falls below 60% of the 30 days before | 86% of the earlier level | Watch |
| The private economy holds its size | The treasury falls more than 60% from its peak | 70% of peak | Holding |
| One key signs for the treasury | More than one key is registered, or the custody setup is published | 1 key | Holding |
| Private totals cannot be audited from outside | NEAR or Intents Technology publishes private volume and fees that an auditor can check | none found, checked 2026-11-07 | Holding |

**The live test.** If private swaps pay NEAR, revenue per dollar holds near 5.32 bps as they grow. If they do
not, it falls toward the part with no private trace, about 1.26 bps. The latest 5 days: 3.92 bps.

We would drop the thesis if NEAR or Intents Technology published private totals that an auditor could check, or if the
share of revenue from the treasury fell back below a quarter.

## What could not be computed

- The private fee itself. No public source gives its rate, and dry quotes for confidential swaps need a partner login. We
  can only see the total lost between entry and exit, which also holds solver spread and price movement.
- Private swap volume. We see money cross the boundary, not swaps inside.
- Who solves private swaps. Solver identity stays on the private chain.
- How the treasury key is held.
- What earned any single revenue payment.
- The value of 33 of the treasury's 193 tokens on past dates, because they have no public price
  history.

## What it means

Private settlement may be the most valuable thing NEAR Intents has shipped this year, and it is the least visible. The
long-term case now rests on three things:

1. Private flow keeps growing.
2. NEAR gets paid for it, without a public rule that says it must.
3. Holders get a way to check.

The first two are bets. The third is a choice, and a cheap one. A daily total reveals nobody's trades.
[The draft proposal](governance/HSP-DRAFT.md) sets out how, and the [weigh station](contract/README.md) already works
without anyone's permission.

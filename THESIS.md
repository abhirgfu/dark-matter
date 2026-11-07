# The thesis: NEAR's best number has gone dark

Research, not financial advice. Every number here is filled in by `python rebuild.py` from raw data in this
repository. Data to 2026-11-07. Dataset hash `e9ae12cefa768cba4b88ea2d6357817aebc287af796b6ae6c6ae35994c16d046`.

## The claim

**NEAR's long-term value now depends on revenue that holders can see arrive but cannot check.**

NEAR's case rests on NEAR Intents earning fees that reach NEAR's wallets. Since September, NEAR has kept about
1.8 times as much of each dollar of volume as it did before, and all of that gain arrived through a
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
call valued it at $141.3M at block 223,474,482, within 0.4% of the $141.9M NEAR
reports. Over 157 days, our daily series built from chain balances and public prices tracks NEAR's with a
correlation of 0.996 and a median gap of 5.1% over the last 60 days. 35% of the priced value
is NEAR itself: 12.5M NEAR, 1.0% of all NEAR in existence.

**Most revenue now comes through it.** We checked 5,083 payments into NEAR's three revenue wallets
against transfers out of the treasury, to the exact yoctoNEAR. Over the last 30 days at least 72% of
revenue dollars left the treasury first. In June it was 0%. The first such payment came on
7 July, the week Confidential Intents opened to all developers. Reading transactions by hand,
33 of 163 sampled payments came from the treasury, through 33 different accounts,
each of which withdrew the same amount to a revenue wallet.

**NEAR keeps more, and all of the gain is private.** In the 60 days before 21 September, revenue
was 2.83 bps of volume and 20% of gross fees. Since then it has been 5.06 bps and
32% of gross fees. The part with no private trace barely moved, from 1.45 to 1.39
bps. The part that left the treasury first went from 1.38 to 3.67 bps. This answers the
question we started with. The API terms say a private company keeps the private fee for its own account, so we expected
a leak. We found the opposite.

**Nobody outside can audit it.** The private chain has no public RPC, API or explorer. Wallet receipts match DefiLlama
within 1.0%, but DefiLlama's revenue is defined as money swept into those wallets, so that check proves only
that money arrived. Selective disclosure is described as planned, not live.

**Control is narrow and undisclosed.** One key is registered for the treasury, the same at all 9 dates we
checked, and it signed 16 of 16 sampled transfers out. The private fee can be set, changed or
removed by Intents Technology alone, at any time, by route, asset or partner. 72% of NEAR's take now arrives
by that route.

## Evidence against

- **The route is not the source.** A payment out of the treasury shows where money came from, not what earned it. A new
  partner deal paid through a shielded account would look the same as fees from private swaps. We cannot rule this out
  from public data.
- **Revenue per dollar has spiked before.** It reached 4.2 bps in June with no private trace,
  then fell back. The current level has held for 47 days, which is not long.
- **The gain may be fading.** Revenue per dollar was 5.32 bps in the 30 days to 26 October and
  4.56 bps in the days since. That window is short.
- **Revenue is still small.** It pays for 22% of the value of new NEAR each day. Even if fully audited, NEAR
  would need $627.8M of daily volume, 4.5 times today's $140.7M, to pay for new NEAR
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
| The private economy holds its size | The treasury falls more than 60% from its peak | 70% of peak | Holding |
| One key signs for the treasury | More than one key is registered, or the custody setup is published | 1 key | Holding |
| Private totals cannot be audited from outside | NEAR or Intents Technology publishes private volume and fees that an auditor can check | none found, checked 2026-11-07 | Holding |

We would drop the thesis if NEAR or Intents Technology published private totals that an auditor could check, or if the
share of revenue from the treasury fell back below a quarter. We would become more worried if revenue per dollar fell back
to its old level while private flow held up, because that would mean private flow had stopped paying NEAR.

## What could not be computed

- The private fee. No public source gives its rate. Dry quotes for confidential swaps need a partner login.
- Private swap volume. We see money cross the boundary, not swaps inside.
- Who solves private swaps. Solver identity stays on the private chain.
- How the treasury key is held.
- What earned any single revenue payment.
- The value of 33 of the treasury's 193 tokens on past dates, because they have no public price
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

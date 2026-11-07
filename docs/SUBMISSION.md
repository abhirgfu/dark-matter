# Submission kit

Everything here waits for you. The organizers' rules say a person must approve each step that is public or
spends money, so nothing below has been done.

## Your checklist, in order

1. **Create a public GitHub repository** called `dark-matter`, then push:

   ```bash
   git remote add origin https://github.com/YOUR-NAME/dark-matter.git
   ```

   ```bash
   git push -u origin main
   ```

2. **Turn on Pages:** Settings, Pages, Source: GitHub Actions. The `pages` workflow then publishes the site to
   `https://YOUR-NAME.github.io/dark-matter/`.

3. **Tell the repo where it lives.** Set `repo_url` and `pages_url` in `data/static/deployment.json`, run
   `python rebuild.py`, commit, and push.

4. **Deploy the contract (recommended).** Follow [contract/README.md](../contract/README.md). It costs about 4 NEAR
   of storage, and it needs your NEAR account. Then set `contract` in `data/static/deployment.json` and rebuild.

5. **Post on X.** Use a draft below, attach the screenshots in `docs/media/`, and publish.

6. **Submit** at https://nearhackathon.com/#apply. You get one submission and cannot edit it. The deadline is
   **14 November 2026, 23:59 UTC**.

Keep the site up until at least 18 November, ideally 25 November.

## Form fields

| Field | Value |
|---|---|
| Project name | Dark Matter |
| Team lead | Your name |
| Email | Your email |
| Team size | Yours |
| Tracks | `thesis`. Also consider `open` |
| NEAR account for the payout | Yours, on mainnet. Nobody else can create this for you |
| Repository | Your GitHub link |
| Demo post | Your X link |
| Consent | Tick it after reading the notice |

### What did you build? (under 2,000 characters)

```text
Problem: NEAR's investment case rests on NEAR Intents revenue, and public dashboards measure it from intents.near logs. But Confidential Intents settles on a private chain with no public RPC or explorer, so dashboards see less of NEAR every day, and revenue can no longer be traced to the swaps that earned it.

Product: Dark Matter measures the private economy from the one public place it has to cross, a single treasury account on intents.near. A live site weighs the treasury from your browser ($141.3M, within 0.4% of NEAR's reported figure). It matched 5,083 revenue payments to treasury transfers, to the exact yoctoNEAR. The finding: at least 72% of NEAR's revenue now arrives from the private treasury. Since September NEAR has kept 5.06 bps of volume, up from 2.83, and all of the gain came by that route. We expected a leak and found the opposite. But nothing public links those payments to swaps, one key signs for the treasury, and the private fee is set off-chain. The thesis lists the evidence against it and tests that can fail. One command, python rebuild.py, rebuilds every number with no keys, then recalculates the headline figures a second way.

NEAR: every number starts from intents.near. A NEAR contract reads the treasury's balances and keys by cross-contract call, with no oracle, and warns on chain if a key changes or money leaves fast. We also give NEAR an open daily feed, an MCP server for agents, and a draft House of Stake proposal for daily totals that reveal nobody's trades.
```

## X post drafts

Lead with the first one. It explains the finding to someone who has never heard of the project.

### Main post

```text
NEAR's revenue per dollar jumped 1.8x this year. In the same weeks, at least 72% of it began arriving from a private chain nobody outside can read.

So the best number in NEAR's investment case is now one you can't check.

I built a way to measure it from the one public place it has to cross.

Built at NEAR HACKATHON. @NEARProtocol #NEARHackathon @NearBuilders
```

### Reply 1

```text
Press "Weigh it yourself" and your browser reads the private treasury straight from intents.near: $141.3M, within 0.4% of what NEAR reports. No server of mine involved.

Every chart shows its query. One command rebuilds every number.

[site link]
```

### Reply 2

```text
I went in expecting private swaps to leak revenue. The data says the opposite: NEAR keeps more.

What breaks is the audit. Wallet receipts now prove money arrived, not what earned it.

So I drafted a proposal for daily totals that reveal nobody's trades, and a contract that weighs the treasury with no oracle.

[repo link]

What would you want published first?
```

## Screenshots

`docs/media/` holds these, made from the real site:

| File | Shows |
|---|---|
| `hero.png` | The headline and live weighing |
| `revenue.png` | The chart at the centre of the thesis |
| `model.png` | The break-even sliders |
| `tests.png` | The tests the thesis can fail |

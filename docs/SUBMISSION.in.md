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

4. **Deploy the contract (recommended).** Follow [contract/README.md](../contract/README.md). It costs about 5 NEAR
   of storage for the first year, and it needs your NEAR account. Then set `contract` in `data/static/deployment.json` and rebuild.

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
{{idea}}
```

## X post drafts

Lead with the first one. It explains the finding to someone who has never heard of the project.

### Main post

```text
NEAR's revenue per dollar jumped {{bps_multiple}}x this year. In the same weeks, at least {{rev_share_recent}} of it began arriving from a private chain nobody outside can read.

So the best number in NEAR's investment case is now one you can't check.

I built a way to measure it from the one public place it has to cross.

Built at NEAR HACKATHON. @NEARProtocol #NEARHackathon @NearBuilders
```

### Reply 1

```text
Press "Weigh it yourself" and your browser reads the private treasury straight from intents.near: {{snapshot_usd}}, within {{snapshot_gap}} of what NEAR reports. No server of mine involved.

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

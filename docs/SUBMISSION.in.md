# Submission kit

Everything here waits for you. The organizers' rules say a person must approve each step that is public or
spends money, so nothing below has been done.

## Your checklist, in order

The rules require a public repository, an X post with a video, a mainnet NEAR account for the payout, and the
form. The hosted site and the contract are not required, but they help.

The BigQuery and Explorer API pulls are done, and their results are in the numbers below. To repeat them, see
[sql/README.md](../sql/README.md) and `pipeline/explorer_check.py`.

1. **Create an empty public GitHub repository** called `dark-matter`, with no README or license, then push:

   ```bash
   git remote add origin https://github.com/YOUR-NAME/dark-matter.git
   ```

   ```bash
   git push -u origin main
   ```

2. **Turn on Pages:** Settings, Pages, Source: GitHub Actions. Then go to Actions, `pages`, Run workflow. The site
   appears at `https://YOUR-NAME.github.io/dark-matter/`.

3. **Tell the repo where it lives.** Set `repo_url` and `pages_url` in `data/static/deployment.json`, run
   `python rebuild.py`, commit, and push.

4. **Make a mainnet NEAR account** for the payout, in any wallet listed at https://wallet.near.org. Keep the
   recovery phrase to yourself.

5. **Deploy the contract (optional).** Follow [contract/README.md](../contract/README.md). It costs about 6 NEAR and
   needs a named account such as `you.near`. Then set `contract` in `data/static/deployment.json` and rebuild.

6. **Post on X.** The post must say it was built at NEAR HACKATHON and tag @NEARProtocol and #NEARHackathon. Use a
   draft below, attach `docs/media/demo.mp4` (a 60-second silent video), and publish. A video you record yourself
   will land better, if you have time.

7. **Submit** at https://nearhackathon.com/#apply. The deadline is **14 November 2026, 23:59 UTC**. You can't edit a
   submission yourself or send a second one for the same repository. Changes go through
   https://nearhackathon.com/request-changes, and the organizers review each one by hand.

Keep the repository public through judging. Keep the site up until at least 18 November, ideally 25 November.

## Form fields

| Field | Value |
|---|---|
| Project name | Dark Matter |
| Team lead | Your name |
| Email | Your email |
| Team size | One of 1, 2 - 4, 4 - 6, 6 - 8, 8+ |
| Tracks | `thesis` |
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
A five-year thesis for NEAR: its long-term value now rests on revenue nobody outside can check.

At least {{rev_share_recent}} of it comes from a private chain, so I measured it from the one public place that money has to cross.

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
The private fee isn't published, but it leaves a fingerprint. Private swaps bunch near {{fee_low}} and {{fee_high}} bps, against a documented public default of 20.

The live test: if private swaps pay NEAR, revenue per dollar holds near {{late_bps_before}} bps. If they don't, it falls toward {{public_floor}}. It's at {{late_bps_after}}.
```

### Reply 3

```text
Wallet receipts now prove money arrived, not what earned it.

So I drafted a House of Stake proposal for daily totals that reveal nobody's trades, and built a contract that weighs the treasury with no oracle.

[repo link]

What would you want published first?
```

## Screenshots

`docs/media/` holds these, made from the real site:

| File | Shows |
|---|---|
| `hero.png` | The headline and live weighing |
| `revenue.png` | The chart at the centre of the thesis |
| `model.png` | The five-year case and the sliders |
| `tests.png` | The tests the thesis can fail |
| `thesis.png` | The long-term thesis in one view |
| `hypothesis.png` | The track's hypothesis and the BigQuery charts |
| `demo.mp4` | A 60-second silent walkthrough with captions |

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
   `python rebuild.py`, commit, and push. The X post drafts below then carry your real links.

4. **Make a mainnet NEAR account** for the payout, in any wallet listed at https://wallet.near.org. Keep the
   recovery phrase to yourself.

5. **Deploy the contract (optional).** Follow [contract/README.md](../contract/README.md). It costs about 6 NEAR and
   needs a named account such as `you.near`. Then set `contract` in `data/static/deployment.json` and rebuild.

6. **Post on X.** The post must say it was built at NEAR HACKATHON and tag @NEARProtocol and #NEARHackathon. Use a
   draft below, attach `docs/media/demo.mp4`, and publish. It is under X's limit of 2 minutes 20 seconds for a
   standard account. Its narration is an AI voice, and the video says so. To use your own voice, follow
   [DEMO_SCRIPT.md](DEMO_SCRIPT.md).

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
The problem: more and more of NEAR's money moves through a private system that nobody outside can read. At least 72% of what NEAR earned in the last 30 days came out of it, so people who hold NEAR can no longer check the number that matters most: whether NEAR is really getting paid.

What we built: Dark Matter, a free tool and five-year investment thesis that measures that private money from public data. One click weighs it live in your browser (about $140.3M), every chart shows its query, 9 public tests say what would prove the thesis wrong, and one command rebuilds every number.

How NEAR fits in: all the money behind the private system sits in one public account on intents.near, so NEAR's public chain is what makes it measurable. A NEAR contract can read the same total on chain, with no oracle.
```

## X post drafts

Post these as one thread, and attach `docs/media/demo.mp4` to the main post. The links fill themselves in once
`data/static/deployment.json` has them. The build checks that each post fits X's limit of 280 characters.

### Main post

```text
How do you judge a crypto network if most of its income is hidden?

We built Dark Matter, a free tool that measures NEAR's private money from the one public account holding it.

Try it: https://abhirgfu.github.io/dark-matter/

Built at NEAR HACKATHON. @NEARProtocol #NEARHackathon @NearBuilders
```

### Reply 1

```text
Press "Weigh it yourself" and your browser reads the total straight from NEAR: about $140.3M. No login, nothing to install.

It works because the money behind NEAR's private system sits in one public account. Anyone can read the total, and nobody's trades are shown.
```

### Reply 2

```text
We also publish what could prove us wrong: 9 public checks, 7 fine so far. And the popular idea that more trading now means more users later barely holds up in our data.

Code and data: https://github.com/abhirgfu/dark-matter

What else would you want to be able to check?
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
| `demo.mp4` | The demo video: the real site, real clicks and a live reading from NEAR, with narration and captions |

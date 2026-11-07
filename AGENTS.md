# For coding agents and AI reviewers

## What this repository is

An investment thesis for NEAR, built at NEAR HACKATHON 2026 (track `thesis`). It measures NEAR's private
economy from public data. Every number in `README.md`, `THESIS.md` and the site is computed from
`data/raw`. None is typed by hand.

## Check it in under a minute

Needs Python 3.10+ and nothing else. No network and no keys.

```bash
python rebuild.py
```

It should end with `ALL CHECKS PASS`. It hash-checks the raw data, recomputes everything, runs the unit
tests, then recalculates the headline numbers a second way with no shared code.

| To verify | Run | Expect |
|---|---|---|
| Raw data is unchanged | `python pipeline/manifest.py check` | `manifest OK` |
| Formulas | `python -m unittest discover -s tests` | `OK` |
| Headline numbers | `python pipeline/verify.py` | `ALL CHECKS PASS` |
| Contract logic | `cd contract && cargo test` | `36 passed` (needs Rust 1.96) |
| Contract builds for NEAR | `cd contract && cargo build --target wasm32-unknown-unknown --release` | `dark_matter.wasm` |
| Live reading | `python pipeline/weigh_now.py` | a value near the site's hero figure (network needed) |
| MCP server | `python -m unittest tests.test_mcp` | `OK` |

## Layout

- `pipeline/metrics.py`: pure formulas, no I/O. Start here.
- `pipeline/analyze.py`: raw data to `data/derived/results.json`.
- `pipeline/falsifiers.py`: the tests the thesis can fail, with their limits.
- `pipeline/build_site.py`: fills `site_src/` and `*.in.md` from computed numbers.
- `pipeline/verify.py`: independent recalculation. Imports nothing from the code above.
- `pipeline/fetch_*.py`: the only files that touch the network.
- `contract/src/lib.rs`: the on-chain weigh station.
- `mcp/server.py`: tools for AI agents.
- `sql/`: BigQuery versions of the chain-wide metrics.

## Rules for changing it

- Edit `README.in.md` and `THESIS.in.md`, never `README.md` or `THESIS.md`, which are generated.
- Numbers go in as `{{placeholders}}` filled from `pipeline/build_site.py`. A missing one stops the build.
- Never keep 1Click or Explorer API data for more than 24 hours. See `docs/METHOD.md`.
- Secrets go in `.env`, which git ignores.

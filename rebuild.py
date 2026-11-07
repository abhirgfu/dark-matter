#!/usr/bin/env python3
"""Rebuild every number, chart and sentence with one command.

    python rebuild.py           from the raw data in this repository (no network, no keys, seconds)
    python rebuild.py --fresh   download fresh public data first (no keys, but rate-limited: slow)

Needs Python 3.10 or newer and nothing else.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
PIPELINE = ROOT / "pipeline"

FRESH = [
    ["fetch_market.py"],
    ["fetch_treasury.py"],
    ["fetch_prices.py", "prices"],
    ["fetch_control.py"],
    ["weigh_now.py"],
    ["fetch_wallets.py", "inflows"],
    ["fetch_flows.py", "plan"],
]


def run(script: str, *args: str) -> None:
    print(f"\n--- {script} {' '.join(args)}".rstrip(), flush=True)
    done = subprocess.run([sys.executable, str(PIPELINE / script), *args], cwd=ROOT)
    if done.returncode:
        sys.exit(done.returncode)


def main() -> int:
    fresh = "--fresh" in sys.argv
    if fresh:
        for step in FRESH:
            run(*step)
        run("manifest.py", "write")
    else:
        run("manifest.py", "check")
    run("analyze.py")
    run("build_site.py")
    print("\n--- tests", flush=True)
    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT)
    if tests.returncode:
        return tests.returncode
    run("verify.py")
    print(f"\nOpen {ROOT / 'site' / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

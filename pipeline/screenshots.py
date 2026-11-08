"""Make the screenshots in docs/media from the real site, with a headless Chromium browser.

For each shot it writes a temporary copy of the page that shows one section, opens it, and deletes it.
The published page is not changed.

    python -m http.server 8765 --directory site     # in another terminal
    python pipeline/screenshots.py
"""
from __future__ import annotations

import glob
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
OUT = ROOT / "docs" / "media"
PORT = 8765
SHOTS = {
    "hero": (None, 1000),
    "revenue": ("revenue", 1160),
    "thesis": ("thesis", 640),
    "model": ("model", 1500),
    "hypothesis": ("activity", 2560),
    "tests": ("tests", 900),
}


def browser() -> str:
    found = shutil.which("msedge") or shutil.which("google-chrome") or shutil.which("chromium")
    if found:
        return found
    for pattern in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        hits = glob.glob(pattern)
        if hits:
            return hits[0]
    sys.exit("No Chromium browser found")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page = (SITE / "index.html").read_text(encoding="utf-8")
    exe = browser()
    profile = tempfile.mkdtemp(prefix="dm-shots-")
    for name, (section, height) in SHOTS.items():
        rule = "html{scroll-behavior:auto!important}"
        if section:
            rule += f"header.hero,.summary:not(#{section} .summary),section.finding:not(#{section}),.thesis-box:not(#{section}),footer{{display:none!important}}"
            rule += f"#{section}{{padding-top:28px!important}}"
        temp = SITE / f"_shot_{name}.html"
        temp.write_text(page.replace("</head>", f"<style>{rule}</style></head>"), encoding="utf-8")
        target = OUT / f"{name}.png"
        try:
            subprocess.run([
                exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={profile}",
                f"--window-size=1280,{height}", "--force-device-scale-factor=2", f"--screenshot={target}",
                "--virtual-time-budget=4000", f"http://localhost:{PORT}/{temp.name}",
            ], check=False, timeout=60, capture_output=True)
        finally:
            temp.unlink(missing_ok=True)
        print(target.name, target.stat().st_size if target.exists() else "missing")
    shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    main()

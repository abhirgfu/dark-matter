"""Make the screenshots in docs/media and a short silent demo video, all from the real site.

Each frame is the real page with one part in view and a caption laid over it. It needs a site server
running, a Chromium browser and `pip install imageio-ffmpeg`.

    python -m http.server 8765 --directory site     # in another terminal
    python pipeline/make_demo.py
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

from common import ROOT, SITE, read_json
from screenshots import PORT, browser

OUT = ROOT / "docs" / "media"
SECONDS = 5.5
WIDTH, HEIGHT = 1280, 720


def frames(n: dict) -> list[tuple[str, str | None, str]]:
    """(name, element to show at the top, caption). The numbers come from the same build as the site."""
    return [
        ("01", None, "NEAR's most important number now comes through a private chain nobody outside can read."),
        ("02", "weigh", "But every private dollar crosses one public account, and your browser can weigh it."),
        ("03", "chart-provenance", f"All of the rise in what NEAR keeps came by the private route: {n['bps_private_before']} to {n['bps_private']} bps."),
        ("04", "chart-swaps", f"On 27 October swaps moved there too. About {n['swaps_multiple']} times as many cross the boundary."),
        ("05", "cost-card", f"The fee is unpublished, but it leaves a fingerprint: price points near {n['fee_low']} and {n['fee_high']} bps."),
        ("06", "keys", f"{n['snapshot_usd']} behind one registered key, with terms that can change at any time."),
        ("07", "tests", f"The thesis can fail. One test is live: the take has moved {n['late_change']} since 27 October."),
        ("08", "for-near", "Daily totals reveal nobody's trades. The proposal and the contract are ready. Every number rebuilds with one command."),
    ]


def page_for(page: str, target: str | None, caption: str) -> str:
    css = (
        "html{scroll-behavior:auto!important}nav.top{display:none}"
        ".dm-cap{position:fixed;left:0;right:0;bottom:0;z-index:50;background:#0d0d0d;color:#f0efec;"
        "font:600 25px system-ui,'Segoe UI',sans-serif;padding:20px 44px 24px;border-top:1px solid rgba(255,255,255,.14);"
        "line-height:1.3;letter-spacing:-.01em}"
    )
    # Headless screenshots ignore scrolling, so the page is slid up instead.
    script = ""
    if target:
        element = "document.querySelector('.weigh')" if target == "weigh" else f"document.getElementById('{target}')"
        click = "document.getElementById('weigh-button').click();" if target == "weigh" else ""
        offset = 96 if target.startswith("chart-") else 16 if target == "weigh" else 40
        script = (
            f"addEventListener('load',()=>{{{click}setTimeout(()=>{{const e={element};"
            f"const y=e.getBoundingClientRect().top+scrollY-{offset};"
            "for(const s of ['header.hero','main','footer'])"
            "document.querySelector(s).style.transform=`translateY(${-y}px)`;"
            "document.body.style.overflow='hidden';},target_delay)});"
        ).replace("target_delay", "3500" if target == "weigh" else "300")
    tail = f"<div class='dm-cap'>{caption}</div><script>{script}</script></body>"
    return page.replace("</head>", f"<style>{css}</style></head>").replace("</body>", tail)


def main() -> int:
    try:
        import imageio_ffmpeg
    except ImportError:
        print("pip install imageio-ffmpeg")
        return 2
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    n = read_json(ROOT / "data" / "derived" / "numbers.json")
    page = (SITE / "index.html").read_text(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path(tempfile.mkdtemp(prefix="dm-demo-"))
    exe = browser()
    images = []
    for name, target, caption in frames(n):
        temp = SITE / f"_demo_{name}.html"
        temp.write_text(page_for(page, target, caption), encoding="utf-8")
        image = work / f"{name}.png"
        try:
            subprocess.run([
                exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={work / 'profile'}",
                f"--window-size={WIDTH},{HEIGHT}", f"--screenshot={image}", "--virtual-time-budget=9000",
                f"http://localhost:{PORT}/{temp.name}",
            ], check=False, timeout=90, capture_output=True)
        finally:
            temp.unlink(missing_ok=True)
        if image.exists():
            images.append(image)
            print(name, image.stat().st_size, flush=True)
    listing = work / "list.txt"
    with open(listing, "w", encoding="utf-8", newline="\n") as fh:
        for image in images:
            fh.write(f"file '{image.as_posix()}'\nduration {SECONDS}\n")
        fh.write(f"file '{images[-1].as_posix()}'\n")
    target = OUT / "demo.mp4"
    subprocess.run([
        ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
        "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "20", "-movflags", "+faststart", str(target),
    ], check=True)
    print(target.name, target.stat().st_size)
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

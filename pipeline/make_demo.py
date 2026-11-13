"""Cut the demo video from the real site: a real browser, a real click, a live reading from NEAR.

The sound comes from pipeline/make_voice.py, so run that first. The timing follows the voice, whether it is
the AI voice or your own recordings. Numbers come from the same build as the site.

    python pipeline/make_demo.py                 # writes docs/media/demo.mp4
    python pipeline/make_demo.py --stills        # a frame every 1.5 seconds in data/local/demo/stills
    python pipeline/make_demo.py --audio-only    # keep the picture and mix the sound again

Needs a Chromium browser and `pip install imageio-ffmpeg`.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import os
import pathlib
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

from common import ROOT, SITE, STATIC, read_json
from demo_script import number
from screenshots import browser

WORK = ROOT / "data" / "local" / "demo"
TARGET = ROOT / "docs" / "media" / "demo.mp4"
FPS = 30
WIDTH, HEIGHT = 1120, 630  # the page's own width, filling a 1920 x 1080 frame
SCALE = 12 / 7
TOP = 54  # the band at the top of the frame kept for the section label
AMBER, GREEN, BLUE, INK = "#fab219", "#3ddc84", "#7fb6ff", "#f0efec"
OFF_SCREEN = (1000.0, 640.0)

# The drawings on the explaining cards.
SHOP = ('<svg viewBox="0 0 120 120" fill="none" stroke="#f0efec" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M16 48 26 18h68l10 30"/><path d="M16 48a11 11 0 0 0 22 0 11 11 0 0 0 22 0 11 11 0 0 0 22 0 11 11 0 0 0 22 0"/>'
        '<path d="M24 62v42h72V62"/><path d="M50 104V78h20v26"/></svg>')
BOX = ('<svg viewBox="0 0 120 120" fill="none" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">'
       '<g stroke="#7fb6ff"><rect x="14" y="36" width="92" height="70" rx="8"/><path d="M14 56h92"/></g>'
       '<g stroke="#fab219"><path d="M51 66v-9a9 9 0 0 1 18 0v9"/><rect x="44" y="66" width="32" height="26" rx="5" fill="#0d0d0d"/></g></svg>')
ARROW = ('<svg viewBox="0 0 90 120" fill="none" stroke="#3ddc84" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">'
         '<text x="35" y="46" fill="#3ddc84" stroke="none" font-size="30" font-weight="800" font-family="system-ui,Segoe UI,sans-serif">$</text>'
         '<path d="M10 62h66M62 50l14 12-14 12"/></svg>')
QUESTION = '<span class="q">?</span>'
ON_SCALE = ('<svg viewBox="0 0 200 170" fill="none" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">'
            '<g stroke="#7fb6ff"><rect x="62" y="6" width="76" height="56" rx="7"/><path d="M62 22h76"/></g>'
            '<g stroke="#fab219"><path d="M93 32v-7a7 7 0 0 1 14 0v7"/><rect x="87" y="32" width="26" height="20" rx="4" fill="#0d0d0d"/></g>'
            '<g stroke="#f0efec"><path d="M36 66h128"/><path d="M48 66 36 160h128L152 66"/><circle cx="100" cy="112" r="28"/></g>'
            '<path id="film-needle" stroke="#3ddc84" stroke-width="5" d="M100 112V90"/></svg>')

# Holds each answer from the public services until the voice gets to it. The answers themselves are not changed.
GATE_JS = """
(() => {
  const real = window.fetch.bind(window);
  const gate = window.__gate = { arrived: 0, released: 0, waiting: [] };
  window.fetch = async (url, options) => {
    const response = await real(url, options);
    const body = await response.text();
    const index = gate.arrived++;
    await new Promise((go) => { if (gate.released > index) go(); else gate.waiting.push([index, go]); });
    return new Response(body, { status: response.status, statusText: response.statusText, headers: response.headers });
  };
  gate.release = () => {
    gate.released += 1;
    gate.waiting = gate.waiting.filter(([i, go]) => { if (gate.released > i) { go(); return false; } return true; });
  };
})();
"""

FILM_JS = r"""
(() => {
  const F = __SPEC__;
  const ease = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));
  const pick = (spec) => { const [sel, up] = spec.split("^"); const el = document.querySelector(sel); return up ? el.closest(up) : el; };
  const during = (t, on, off, fade) => Math.min(ease((t - on) / fade), ease((off - t) / fade));
  const sans = 'system-ui,"Segoe UI",sans-serif';
  const sheet = document.createElement("style");
  sheet.textContent = `
    html{scroll-behavior:auto!important} nav.top{display:none!important} body{overflow:hidden}
    #film-spot,#film-cap,.film-call,#film-cursor,#film-ring,#film-end,#film-title,#film-label,#film-chips{pointer-events:none}
    #film-title{position:fixed;inset:0;z-index:57;display:grid;place-items:center;padding:34px 80px 30px;opacity:0;font-family:${sans};
      background:radial-gradient(circle at 84% 22%,#0d0d0d 0 13%,rgba(57,135,229,.2) 14%,rgba(57,135,229,.05) 19%,transparent 28%),#0d0d0d}
    #film-title>div{grid-area:1/1;display:flex;flex-direction:column;align-items:center;gap:22px;opacity:0}
    #film-title p{margin:0;font-size:56px;font-weight:800;line-height:1.12;letter-spacing:-.03em;color:#f7f6f2;text-align:center;max-width:960px}
    #film-title .art{display:flex;align-items:center;justify-content:center;gap:22px}
    #film-title .art svg{height:176px;width:auto}
    #film-title .q{font-size:150px;font-weight:800;line-height:1;color:#fab219}
    #film-label{position:fixed;top:12px;left:18px;z-index:59;font:700 18px/1.2 ${sans};color:#7fb6ff;background:rgba(13,13,13,.94);
      border:1px solid rgba(127,182,255,.45);border-radius:8px;padding:6px 12px;opacity:0}
    #film-chips{position:fixed;top:12px;left:0;right:0;z-index:59;display:flex;justify-content:center;gap:10px;opacity:0}
    #film-chips span{font:600 17px/1.2 ${sans};color:#b9b8ae;background:rgba(13,13,13,.94);border:1px solid rgba(255,255,255,.2);border-radius:999px;padding:7px 15px}
    #film-chips span.on{color:#0b0b0b;background:#7fb6ff;border-color:#7fb6ff}
    #film-spot{position:fixed;z-index:40;border-radius:14px;opacity:0;
      box-shadow:0 0 0 3px #3987e5,0 0 46px 8px rgba(57,135,229,.34),0 0 0 4000px rgba(6,6,6,.68)}
    #film-cap{position:fixed;left:0;right:0;bottom:0;z-index:60;display:flex;justify-content:center;padding:44px 34px 18px;
      background:linear-gradient(to top,rgba(8,8,8,.97) 58%,rgba(8,8,8,0));opacity:0}
    #film-cap span{font:600 29px/1.26 ${sans};letter-spacing:-.012em;color:#f7f6f2;text-align:center;max-width:1020px}
    #film-cap b{font-weight:750;color:#8fc1ff}
    .film-call{position:fixed;z-index:55;padding:15px 24px 16px;background:rgba(13,13,13,.96);border:1px solid rgba(255,255,255,.2);
      border-radius:16px;box-shadow:0 16px 44px rgba(0,0,0,.65);opacity:0;visibility:hidden;font-family:${sans}}
    .film-call .big{font-weight:800;font-size:66px;line-height:1;letter-spacing:-.035em}
    .film-call .small{font-weight:500;font-size:20px;line-height:1.25;color:#d5d4cb;margin-top:7px;max-width:330px}
    #film-cursor{position:fixed;left:0;top:0;z-index:70;width:34px;height:34px;opacity:0}
    #film-ring{position:fixed;left:0;top:0;z-index:69;width:44px;height:44px;border-radius:50%;border:3px solid #7fb6ff;opacity:0}
    #film-end{position:fixed;inset:0;z-index:58;background:#0d0d0d;display:flex;flex-direction:column;justify-content:center;align-items:center;
      opacity:0;font-family:${sans};text-align:center;padding:0 60px 40px}
    #film-end h2{font-size:58px;line-height:1.1;letter-spacing:-.03em;margin:0 0 26px;font-weight:800;color:#f7f6f2}
    #film-end .name{font-size:30px;font-weight:700;color:#7fb6ff;margin:0 0 8px}
    #film-end .small{font-size:20px;color:#a9a89f;margin:4px 0}
  `;
  document.head.append(sheet);
  const make = (id, cls) => { const d = document.createElement("div"); if (id) d.id = id; if (cls) d.className = cls; document.body.append(d); return d; };
  const spot = make("film-spot"), cap = make("film-cap"), cursor = make("film-cursor"), ring = make("film-ring"), end = make("film-end"), title = make("film-title"),
    label = make("film-label"), chips = make("film-chips");
  const cards = F.titles.map((x) => { const d = document.createElement("div"); d.innerHTML = x.html; title.append(d); return d; });
  const needle = document.getElementById("film-needle");
  chips.innerHTML = F.chips.items.map((c) => `<span>${c.text}</span>`).join("");
  const chipRows = [...chips.children];
  cap.innerHTML = "<span></span>";
  cursor.innerHTML = '<svg viewBox="0 0 24 24" width="34" height="34"><path d="M4 2l16 11.5-7.2 1.3-4 6.7z" fill="#fff" stroke="#0a0a0a" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  end.innerHTML = F.end.html;
  const question = end.querySelector("h2");
  const calls = F.calls.map((c) => {
    const d = make(null, "film-call");
    d.innerHTML = `<div class="big" style="color:${c.color}">${c.big}</div><div class="small">${c.small}</div>`;
    Object.assign(d.style, c.place);
    return d;
  });
  window.__film = {
    clickAt: -9,
    seek(t, cx, cy, cursorOn) {
      let previous = 0, y = 0;
      const most = document.documentElement.scrollHeight - innerHeight;
      for (const shot of F.camera) {
        if (t < shot.at) break;
        const box = shot.el === "top" ? null : pick(shot.el).getBoundingClientRect();
        const goal = box ? Math.max(0, Math.min(most, box.top + scrollY - shot.offset)) : 0;
        y = shot.ease ? previous + (goal - previous) * ease((t - shot.at) / shot.ease) : goal;
        previous = goal;
      }
      scrollTo(0, y);
      let best = null, strength = 0;
      for (const s of F.spots) { const a = during(t, s.on, s.off, 0.3); if (a > strength) { strength = a; best = s; } }
      let spotKey = "";
      if (best) {
        const r = pick(best.el).getBoundingClientRect(), pad = best.pad ?? 10;
        spot.style.left = `${r.left - pad}px`; spot.style.top = `${r.top - pad}px`;
        spot.style.width = `${r.width + pad * 2}px`; spot.style.height = `${r.height + pad * 2}px`;
        spotKey = `${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.width)},${Math.round(r.height)}`;
      }
      spot.style.opacity = strength;
      let text = "", capOn = 0;
      for (const c of F.captions) if (t >= c.on && t <= c.off) { text = c.html; capOn = during(t, c.on, c.off, 0.1); }
      if (cap.dataset.text !== text) { cap.firstChild.innerHTML = text; cap.dataset.text = text; }
      cap.style.opacity = capOn;
      const callKey = F.calls.map((c, i) => {
        const a = during(t, c.on, c.off, 0.28), el = calls[i];
        el.style.opacity = a; el.style.visibility = a > 0 ? "visible" : "hidden";
        el.style.transform = `translateY(${(1 - a) * 14}px) scale(${0.96 + a * 0.04})`;
        return a.toFixed(3);
      }).join();
      const glowKey = F.glows.map((g) => {
        const a = during(t, g.on, g.off, 0.4), el = pick(g.el);
        el.style.textShadow = a > 0 ? `0 0 ${28 * a}px rgba(127,182,255,${0.95 * a})` : "";
        return a.toFixed(3);
      }).join();
      const dimKey = F.dims.map((d) => {
        const a = during(t, d.on, d.off, 0.3);
        pick(d.el).style.opacity = 1 - a * (1 - d.to);
        return a.toFixed(3);
      }).join();
      const cardOn = Math.max(0, ...F.blocks.map((b) => during(t, b.on, b.off, 0.45)));
      title.style.opacity = cardOn;
      const cardKey = F.titles.map((x, i) => { const a = during(t, x.on, x.off, 0.22); cards[i].style.opacity = a; return a.toFixed(3); }).join();
      const swing = ease((t - F.needle) / 0.9);
      needle.setAttribute("transform", `rotate(${-75 + 115 * swing} 100 112)`);
      let name = "", nameOn = 0;
      for (const l of F.labels) if (t >= l.on && t <= l.off) { name = l.text; nameOn = during(t, l.on, l.off, 0.2); }
      if (label.textContent !== name) label.textContent = name;
      label.style.opacity = nameOn;
      const chipsOn = during(t, F.chips.on, F.chips.off, 0.25);
      chips.style.opacity = chipsOn;
      let active = -1;
      F.chips.items.forEach((c, i) => { if (t >= c.at) active = i; });
      chipRows.forEach((row, i) => row.classList.toggle("on", i === active));
      const endOn = ease((t - F.end.on) / 0.7), questionOn = ease((t - F.end.question) / 0.5);
      end.style.opacity = endOn; question.style.opacity = questionOn;
      cursor.style.opacity = cursorOn; cursor.style.transform = `translate(${cx}px,${cy}px)`;
      const since = t - this.clickAt, ringOn = since >= 0 && since < 0.6 ? 1 - since / 0.6 : 0;
      ring.style.opacity = ringOn; ring.style.transform = `translate(${cx - 22}px,${cy - 22}px) scale(${0.35 + since * 2})`;
      return [dimKey, cardOn.toFixed(3), cardKey, swing.toFixed(3), Math.round(y), spotKey, strength.toFixed(3), text, capOn.toFixed(2), callKey, glowKey, name, nameOn.toFixed(2),
        chipsOn.toFixed(3), active, endOn.toFixed(3), questionOn.toFixed(3), Math.round(cx), Math.round(cy), cursorOn, ringOn.toFixed(3),
        document.getElementById("weigh-log").textContent.length, document.getElementById("weigh-value").textContent].join("|");
    },
  };
})();
"""


class Tab:
    """Just enough of the browser's debugging protocol, over a plain socket."""

    def __init__(self, url: str):
        parts = urllib.parse.urlsplit(url)
        self.sock = socket.create_connection((parts.hostname, parts.port))
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {parts.path} HTTP/1.1\r\nHost: {parts.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        self.stream = self.sock.makefile("rb")
        while self.stream.readline().strip():
            pass
        self.count = 0

    def _send(self, payload: bytes) -> None:
        mask = os.urandom(4)
        size = len(payload)
        head = bytes([0x81]) + (bytes([0x80 | size]) if size < 126 else bytes([0x80 | 126]) + struct.pack(">H", size) if size < 65536 else bytes([0x80 | 127]) + struct.pack(">Q", size))
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def _receive(self) -> bytes:
        message = b""
        while True:
            first, second = self.stream.read(2)
            size = second & 0x7F
            if size == 126:
                size = struct.unpack(">H", self.stream.read(2))[0]
            elif size == 127:
                size = struct.unpack(">Q", self.stream.read(8))[0]
            data = self.stream.read(size)
            if first & 0x0F in (0, 1, 2):
                message += data
                if first & 0x80:
                    return message

    def call(self, method: str, **params) -> dict:
        self.count += 1
        self._send(json.dumps({"id": self.count, "method": method, "params": params}).encode())
        while True:
            reply = json.loads(self._receive())
            if reply.get("id") == self.count:
                if "error" in reply:
                    raise RuntimeError(f"{method}: {reply['error']}")
                return reply.get("result", {})

    def run(self, expression: str):
        result = self.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in result:
            raise RuntimeError(f"{expression[:80]}: {result['exceptionDetails']}")
        return result["result"].get("value")

    def mouse(self, kind: str, x: float, y: float, **extra) -> None:
        self.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, **extra)

    def rect(self, selector: str) -> dict:
        return self.run(f"(() => {{const r = document.querySelector({json.dumps(selector)}).getBoundingClientRect(); return {{x: r.left, y: r.top, w: r.width, h: r.height}};}})()")

    def frame(self) -> bytes:
        return base64.b64decode(self.call("Page.captureScreenshot", format="jpeg", quality=94, fromSurface=True)["data"])


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def open_site(profile: str) -> tuple[list[subprocess.Popen], Tab]:
    site_port, debug_port = free_port(), free_port()
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(site_port), "--bind", "127.0.0.1", "--directory", str(SITE)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome = subprocess.Popen([browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--mute-audio", "--no-first-run",
                               f"--remote-debugging-port={debug_port}", f"--user-data-dir={profile}", "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    tab = None
    for _ in range(150):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json/list", timeout=2) as resp:
                tab = next(t for t in json.load(resp) if t["type"] == "page")
            with urllib.request.urlopen(f"http://127.0.0.1:{site_port}/", timeout=2):
                break
        except (OSError, StopIteration):
            time.sleep(0.2)
    if tab is None:
        sys.exit("The browser did not start")
    page = Tab(tab["webSocketDebuggerUrl"])
    page.call("Page.enable")
    page.call("Runtime.enable")
    page.call("Emulation.setDeviceMetricsOverride", width=WIDTH, height=HEIGHT, deviceScaleFactor=SCALE, mobile=False)
    page.call("Page.addScriptToEvaluateOnNewDocument", source=GATE_JS)
    page.call("Page.navigate", url=f"http://127.0.0.1:{site_port}/")
    for _ in range(150):
        if page.run("document.readyState") == "complete" and page.run("document.querySelectorAll('svg').length") > 5:
            break
        time.sleep(0.1)
    time.sleep(0.8)
    return [server, chrome], page


def stop(processes: list[subprocess.Popen], profile: str) -> None:
    for process in processes:
        process.kill()
    if os.name == "nt":  # the browser's helpers outlive it, so find them by the profile folder they share
        script = ("Get-CimInstance Win32_Process -Filter \"Name='msedge.exe' OR Name='chrome.exe'\" | "
                  f"Where-Object {{ $_.CommandLine -match '{pathlib.Path(profile).name}' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}")
        subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True)
    time.sleep(1)
    shutil.rmtree(profile, ignore_errors=True)


def caption_html(text: str) -> str:
    return re.sub(r"(\$?\d[\d,.]*\d|\$?\d)(%| billion| million| times)?", lambda m: f"<b>{m.group(0)}</b>", html.escape(text, quote=False))


def card(art: str, text: str) -> str:
    picture = f'<div class="art">{art}</div>' if art else ""
    return f"{picture}<p>{html.escape(text, quote=False)}</p>"


def build_spec(timeline: dict, n: dict) -> dict:
    takes = {t["name"]: t for t in timeline["takes"]}
    m = {line["mark"]: line for t in timeline["takes"] for line in t["lines"]}
    start = lambda mark: m[mark]["start"]  # noqa: E731
    stop_at = lambda mark: m[mark]["end"]  # noqa: E731
    show = lambda mark: m[mark]["show"]  # noqa: E731
    chart_gap = {"left": "420px", "top": "160px"}  # where the bars are low
    path_gap = {"left": "132px", "top": "156px"}  # the lines only climb later
    beside_box = {"left": "718px", "top": "146px"}
    camera = [
        {"at": 0, "el": "top", "offset": 0, "ease": 0},
        {"at": stop_at("today") + 0.02, "el": "#chart-history^.card", "offset": TOP, "ease": 0},  # behind the card, so nobody sees the jump
        {"at": start("share") - 0.25, "el": ".summary", "offset": TOP + 8, "ease": 0.8},
        {"at": start("cant") - 0.2, "el": "top", "offset": 0, "ease": 0.5},
        {"at": start("cantopen") + 0.2, "el": ".weigh", "offset": TOP, "ease": 0},
        {"at": start("second") - 0.15, "el": "#chart-provenance^.card", "offset": TOP, "ease": 0.9},
        {"at": start("tests") - 0.2, "el": "#tests table", "offset": TOP, "ease": 0.9},
        {"at": takes["honest"]["start"] - 0.1, "el": "#chart-lag^.card", "offset": TOP, "ease": 0.9},
        {"at": start("verdict") - 0.55, "el": "#activity", "offset": TOP + 4, "ease": 0.5},
        {"at": takes["maths"]["start"] - 0.1, "el": "#chart-path^.card", "offset": TOP, "ease": 0.9},
    ]
    spots = [
        {"on": start("share"), "off": stop_at("share") + 0.4, "el": ".summary .tile", "pad": 8},
        {"on": start("cant") + 0.2, "off": stop_at("cant") + 0.3, "el": ".lede strong", "pad": 8},
        {"on": start("built") + 0.2, "off": stop_at("built") + 0.45, "el": "h1", "pad": 14},
        {"on": start("cross"), "off": stop_at("weight") + 0.5, "el": ".weigh", "pad": 10},
        {"on": start("first"), "off": stop_at("first") + 0.3, "el": "#weigh-button", "pad": 10},
        {"on": start("states"), "off": stop_at("states") + 0.4, "el": "#tests table", "pad": 4},
        {"on": start("verdict") - 0.05, "off": stop_at("page") + 0.4, "el": "#activity h2", "pad": 12},
    ]
    floor, trend = (round(number(n[k])) for k in ("needed_floor", "observed_growth"))
    calls = [
        {"on": start("share") + 0.2, "off": stop_at("share") + 0.3, "big": f"{n['rev_share_recent']}+", "small": "of what NEAR earned in the last 30 days came out of the private system", "color": AMBER, "place": {"left": "36px", "top": "250px"}},
        {"on": start("built") + 0.4, "off": stop_at("built") + 0.45, "big": "Dark Matter", "small": "A free tool that measures the private money on NEAR", "color": BLUE, "place": {"right": "44px", "top": "352px"}},
        {"on": start("cross") + 0.4, "off": stop_at("cross") + 0.5, "big": "1", "small": "public account holds all the money behind the private system", "color": BLUE, "place": beside_box},
        {"on": start("result") + 0.25, "off": stop_at("weight") + 0.5, "big": "LIVE", "small": 'read from NEAR just now, at block <span id="film-block"></span>', "color": GREEN, "place": beside_box},
        {"on": start("before") + 0.15, "off": start("after"), "big": f"${n['bps_before']}", "small": "NEAR's earnings on every $10,000 traded", "color": INK, "place": chart_gap},
        {"on": start("after") + 0.05, "off": stop_at("after") + 0.4, "big": f"${n['bps_after']}", "small": "NEAR's earnings on every $10,000 traded", "color": GREEN, "place": chart_gap},
        {"on": stop_at("need") - 3.6, "off": start("lately"), "big": f"{floor}%+", "small": "growth needed each year", "color": INK, "place": path_gap},
        {"on": start("lately") + 0.05, "off": stop_at("promised") + 0.3, "big": f"{trend}%", "small": "growth over the last year", "color": GREEN, "place": path_gap},
    ]
    on_cards = ("shop", "box", "open", "know", "today", "cantopen", "scale", "check")  # the card says these, so no caption
    captions = [{"on": line["start"] - 0.06, "off": line["end"] + 0.22, "html": caption_html(line["show"])}
                for take in timeline["takes"] for line in take["lines"] if line["mark"] not in on_cards]
    titles = [
        {"on": -1, "off": start("box") - 0.05, "html": card(SHOP, show("shop"))},
        {"on": start("box") - 0.05, "off": start("open") - 0.05, "html": card(SHOP + ARROW + BOX, show("box"))},
        {"on": start("open") - 0.05, "off": start("know") - 0.05, "html": card(BOX, show("open"))},
        {"on": start("know") - 0.05, "off": start("today") - 0.05, "html": card(SHOP + QUESTION, show("know"))},
        {"on": start("today") - 0.05, "off": stop_at("today") + 0.5, "html": card("", show("today"))},
        {"on": start("cantopen") - 0.1, "off": start("scale") - 0.05, "html": card(BOX, show("cantopen"))},
        {"on": start("scale") - 0.05, "off": stop_at("scale") + 0.55, "html": card(ON_SCALE, show("scale"))},
        {"on": start("check") - 0.1, "off": start("link") + 0.6, "html": card("", show("check"))},
    ]
    blocks = [{"on": -1, "off": stop_at("today") + 0.5}, {"on": start("cantopen") - 0.5, "off": stop_at("scale") + 0.55},
              {"on": start("check") - 0.5, "off": start("link") + 0.6}]
    ordered = timeline["takes"]
    labels = [{"on": -1 if i == 0 else take["start"] - 0.2, "off": ordered[i + 1]["start"] - 0.2 if i + 1 < len(ordered) else 9999, "text": take["label"]}
              for i, take in enumerate(ordered)]
    chips = {"on": start("first") - 0.25, "off": takes["benefit"]["end"] + 0.05, "items": [
        {"at": start("first") - 0.25, "text": "Check it yourself"},
        {"at": start("second") - 0.15, "text": "See if NEAR gets paid"},
        {"at": start("tests") - 0.15, "text": "Checks that could show we're wrong"},
    ]}
    credit = "Narration: AI voice. " if timeline["voice"].startswith("kokoro") else ""
    repo = read_json(STATIC / "deployment.json").get("repo_url")
    end_html = (
        '<h2>What else would you want to check?</h2><p class="name">Dark Matter</p>'
        + '<p class="small">A free tool that measures the private money on NEAR</p>'
        + (f'<p class="small">{html.escape(repo)}</p>' if repo else "")
        + f'<p class="small">{credit}Research, not financial advice.</p>'
    )
    return {
        "camera": camera, "spots": spots, "calls": calls, "captions": captions, "titles": titles, "blocks": blocks, "labels": labels, "chips": chips,
        "needle": start("scale") + 0.15,
        "glows": [{"on": start("result") - 0.1, "off": timeline["duration"], "el": "#weigh-value"}],
        "dims": [{"on": start("click") + 0.15, "off": start("result") - 0.15, "el": "#weigh-value", "to": 0.22}],
        "end": {"on": start("link") - 0.1, "question": start("mind") - 0.25, "html": end_html},
    }


class Director:
    """Runs the real click and the cursor, in step with the voice."""

    def __init__(self, page: Tab, timeline: dict, spoken_usd: float):
        self.page = page
        m = {line["mark"]: line for t in timeline["takes"] for line in t["lines"]}
        self.spoken_usd = spoken_usd
        self.x, self.y = OFF_SCREEN
        self.path: tuple | None = None
        click = m["click"]["start"] + 0.12
        self.events = [
            (m["watch"]["start"] - 0.1, self.to_button),
            (click, self.press_button),
            (click + 1.1, lambda t: self.release(1)),
            (click + 2.3, lambda t: self.release(2)),
            (m["result"]["start"] - 0.2, self.finish_weigh),
        ]
        self.fades = [(m["watch"]["start"] - 0.1, 1.0), (m["noserver"]["end"] + 0.4, 0.0)]

    def opacity(self, t: float) -> float:
        value = 0.0
        for at, target in self.fades:
            if t >= at:
                value = value + (target - value) * min((t - at) / 0.25, 1.0)
                value = target if t - at >= 0.25 else value
        return round(value, 2)

    def position(self, t: float) -> tuple[float, float]:
        if self.path:
            begin, seconds, x0, y0, x1, y1 = self.path
            k = min(max((t - begin) / seconds, 0), 1)
            k = k * k * (3 - 2 * k)
            self.x, self.y = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
            if k >= 1:
                self.path = None
        return self.x, self.y

    def to_button(self, t: float) -> None:
        r = self.page.rect("#weigh-button")
        self.path = (t, 1.0, self.x, self.y, r["x"] + r["w"] * 0.55, r["y"] + r["h"] * 0.55)

    def press_button(self, t: float) -> None:
        x, y = self.position(t)
        self.page.mouse("mouseMoved", x, y)
        self.page.mouse("mousePressed", x, y, button="left", clickCount=1)
        self.page.mouse("mouseReleased", x, y, button="left", clickCount=1)
        self.page.run(f"window.__film.clickAt = {t}")

    def release(self, count: int) -> None:
        for _ in range(600):
            if self.page.run("window.__gate.arrived") >= count:
                break
            time.sleep(0.05)
        else:
            sys.exit("A public service did not answer in time")
        self.page.run("window.__gate.release()")
        time.sleep(0.08)

    def finish_weigh(self, t: float) -> None:
        self.release(3)
        for _ in range(400):
            note = self.page.run("document.getElementById('weigh-note').textContent")
            if note.startswith("Weighed just now"):
                break
            if self.page.run("window.__gate.arrived > window.__gate.released"):
                self.page.run("window.__gate.release()")
            time.sleep(0.05)
        else:
            sys.exit("The live weighing did not finish: " + str(self.page.run("document.getElementById('weigh-log').textContent")))
        live = self.page.run("document.getElementById('weigh-value').textContent")
        if abs(number(live) - self.spoken_usd) > 2.5:
            sys.exit(f"The live reading is {live}, too far from the ${self.spoken_usd:.0f}M the voice says")
        self.page.run("document.getElementById('film-block').textContent = document.getElementById('weigh-note').textContent.match(/block ([\\d,]*\\d)/)[1]")
        print("live reading", live, flush=True)

    def step(self, t: float) -> bool:
        """Do what is due by time t. True if the page was touched."""
        touched = False
        while self.events and self.events[0][0] <= t:
            _, action = self.events.pop(0)
            action(t)
            touched = True
        return touched


def ffmpeg_exe() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def film(page: Tab, spec: dict, timeline: dict, n: dict, stills: bool) -> None:
    page.run(FILM_JS.replace("__SPEC__", json.dumps(spec)))
    director = Director(page, timeline, number(n["snapshot_usd"]))
    total = int(timeline["duration"] * FPS)
    still_every = int(FPS * 1.5)
    folder = WORK / "stills"
    encoder = None
    if stills:
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
    else:
        encoder = subprocess.Popen([
            ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
            "-vf", "scale=in_color_matrix=bt601:in_range=pc:out_color_matrix=bt709:out_range=tv,format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            str(WORK / "picture.mp4"),
        ], stdin=subprocess.PIPE)
    last_key, last_frame = None, None
    began = time.time()
    for i in range(total):
        t = i / FPS
        touched = director.step(t)
        x, y = director.position(t)
        key = page.run(f"window.__film.seek({t}, {x}, {y}, {director.opacity(t)})")
        if stills:
            if i % still_every == 0:
                (folder / f"{t:06.1f}.jpg").write_bytes(page.frame())
            continue
        if key != last_key or touched or last_frame is None:
            last_frame = page.frame()
            last_key = key
        encoder.stdin.write(last_frame)
        if i % 300 == 0:
            print(f"{t:.0f} of {timeline['duration']:.0f} s, {time.time() - began:.0f} s so far", flush=True)
    if encoder:
        encoder.stdin.close()
        if encoder.wait():
            sys.exit("The video encoder failed")


def loudness(graph: str, inputs: list[str]) -> dict:
    done = subprocess.run([ffmpeg_exe(), "-hide_banner", "-nostats", *inputs, "-filter_complex", f"{graph},loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                          capture_output=True, text=True, check=True)
    return json.loads(done.stderr[done.stderr.rindex("{"): done.stderr.rindex("}") + 1])


def finish() -> None:
    inputs = ["-i", str(WORK / "voice.wav"), "-i", str(WORK / "music.wav")]
    graph = "[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0[v];[v][1:a]amix=inputs=2:normalize=0:duration=longest"
    level = loudness(graph, inputs)
    second = (f"{graph},loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:measured_I={level['input_i']}:measured_TP={level['input_tp']}:"
              f"measured_LRA={level['input_lra']}:measured_thresh={level['input_thresh']}:offset={level['target_offset']}")
    mix = WORK / "mix.wav"
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", *inputs, "-filter_complex", second, "-ar", "48000", "-c:a", "pcm_s16le", str(mix)], check=True)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(WORK / "picture.mp4"), "-i", str(mix), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(TARGET)], check=True)
    print(f"{TARGET.relative_to(ROOT)}: {TARGET.stat().st_size / 1e6:.1f} MB, loudness measured {level['input_i']} LUFS before levelling")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stills", action="store_true")
    parser.add_argument("--audio-only", action="store_true")
    args = parser.parse_args()
    if not (WORK / "timeline.json").exists():
        sys.exit("Run pipeline/make_voice.py first")
    if args.audio_only:
        finish()
        return 0
    timeline = read_json(WORK / "timeline.json")
    n = read_json(ROOT / "data" / "derived" / "numbers.json")
    profile = tempfile.mkdtemp(prefix="dm-film-")
    processes, page = open_site(profile)
    try:
        film(page, build_spec(timeline, n), timeline, n, args.stills)
    finally:
        stop(processes, profile)
    if not args.stills:
        finish()
    return 0


if __name__ == "__main__":
    sys.exit(main())

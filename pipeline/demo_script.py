"""The words of the demo video, for someone who has never heard of NEAR, filled from the computed numbers.

The video is cut into takes, and each take is a few lines. `say` is what the AI voice reads, with numbers
spelled out so nothing is mispronounced. `show` is the caption, and what a person reads from when recording
it themselves. `mood` sets the delivery.

    python pipeline/demo_script.py      # writes docs/DEMO_SCRIPT.md
"""
from __future__ import annotations

import datetime as dt
import sys

from common import DERIVED, ROOT, read_json

# speed and pitch are for the AI voice, as a multiple of normal and a fraction up or down.
# gain is in decibels. cue is the note a person reads when recording it themselves.
MOODS = {
    "plain": {"speed": 0.88, "pitch": 0.000, "gain": 0.0, "cue": "friendly, like talking to one person"},
    "ask": {"speed": 0.86, "pitch": 0.012, "gain": 0.0, "cue": "a real question"},
    "heavy": {"speed": 0.85, "pitch": -0.025, "gain": -1.5, "cue": "slower and lower, this is bad news"},
    "turn": {"speed": 0.88, "pitch": 0.015, "gain": 1.0, "cue": "lean in, something is about to happen"},
    "wow": {"speed": 0.96, "pitch": 0.04, "gain": 2.0, "cue": "real surprise, smiling"},
    "hush": {"speed": 0.86, "pitch": -0.01, "gain": -3.0, "cue": "nearly a whisper"},
    "awe": {"speed": 0.88, "pitch": 0.02, "gain": 0.5, "cue": "slow, amazed"},
    "warm": {"speed": 0.87, "pitch": 0.01, "gain": 0.0, "cue": "warm and sure"},
    "firm": {"speed": 0.83, "pitch": -0.01, "gain": 0.5, "cue": "firm, you are proud of this"},
    "plea": {"speed": 0.86, "pitch": 0.015, "gain": 0.0, "cue": "smiling, you mean it"},
}

SMALL = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
         "sixteen seventeen eighteen nineteen").split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def words(n: int) -> str:
    """0 to 999 in words."""
    if n < 20:
        return SMALL[n]
    if n < 100:
        return TENS[n // 10] + (f"-{SMALL[n % 10]}" if n % 10 else "")
    if n < 1000:
        head = "a hundred" if n // 100 == 1 else f"{SMALL[n // 100]} hundred"
        return head + (f" and {words(n % 100)}" if n % 100 else "")
    raise ValueError(n)


def number(text: str) -> float:
    """The number in a figure such as +46%, −14%, $140.3M or 3.7."""
    return float(text.strip("+−-$%MBKx× "))


def bare(text: str) -> str:
    """76% -> seventy-six"""
    return words(round(abs(number(text))))


def millions(text: str) -> str:
    """$140.3M -> a hundred and forty million dollars"""
    return f"{words(round(number(text)))} million dollars"


def cash(text: str) -> str:
    """2.83 -> two dollars eighty-three, 5.06 -> five dollars and six cents"""
    whole, _, rest = text.partition(".")
    dollars, cents = int(whole), int((rest + "00")[:2])
    name = f"{words(dollars)} dollar{'' if dollars == 1 else 's'}"
    if cents == 0:
        return name
    return f"{name} {words(cents)}" if cents >= 10 else f"{name} and {words(cents)} cents"


def part_of_month(iso_day: str) -> str:
    day = dt.date.fromisoformat(iso_day).day
    return "early" if day <= 10 else "mid" if day <= 20 else "late"


def check_story(n: dict, tests: list[dict]) -> None:
    """The words assume these results. If one changes, the script has to be rewritten, not just refilled."""
    states = [t["state"] for t in tests]
    links = [abs(float(n[k].replace("−", "-"))) for k in ("h_accounts_v", "h_txns_v", "h_calls_v")]
    problems = [
        ("the hypothesis is no longer rejected", n["h_verdict"] != "Not supported"),
        ("swapping now clearly predicts usage", max(links) >= 0.3),
        ("volume growth no longer clears the bar", number(n["observed_growth"]) <= number(n["needed_cap"])),
        ("the private route no longer brings most of the earnings", number(n["rev_share_recent"]) <= 50),
        ("the rise in earnings is no longer almost double", not 1.6 <= number(n["bps_multiple"]) < 2),
        ("a test has broken", "broken" in states),
        ("the counts of watched or pending tests changed", states.count("watch") != 1 or states.count("pending") != 1),
    ]
    found = [text for text, bad in problems if bad]
    if found:
        sys.exit("The demo script no longer fits the results: " + "; ".join(found))


def line(mood: str, mark: str, say: str, show: str | None = None, pause: float = 0.32) -> dict:
    """`mark` names the line, so the picture can follow it."""
    return {"mood": mood, "mark": mark, "say": say, "show": show or say.replace("Near", "NEAR"), "pause": pause}


def takes(n: dict, tests: list[dict]) -> list[dict]:
    check_story(n, tests)
    states = [t["state"] for t in tests]
    usd = round(number(n["snapshot_usd"]))
    month = f"{part_of_month(n['era_start'])} {n['era_month']}"
    now = round(number(n["bps_after"]))
    floor, trend = (round(number(n[k])) for k in ("needed_floor", "observed_growth"))
    return [
        {"name": "problem", "label": "The problem", "lines": [
            line("plain", "shop", "Imagine you're putting your money into a shop.", pause=0.35),
            line("plain", "box", "One day, most of its income starts going through a locked box.", pause=0.3),
            line("hush", "open", "Nobody outside can open it.", pause=0.45),
            line("ask", "know", "How would you know the shop is doing well?", pause=0.6),
            line("firm", "today", "That's the problem with Near today.", pause=0.55),
            line("plain", "fee", "Near is a blockchain: an online network where people trade digital coins. It earns a small fee when they do."),
            line("heavy", "share", f"But now, at least {bare(n['rev_share_recent'])} percent of what it earns comes out of a private system nobody outside can read.",
                 f"But now, at least {n['rev_share_recent']} of what it earns comes out of a private system nobody outside can read.", pause=0.4),
            line("heavy", "cant", "So if you hold Near coins, you can't check the number that matters most.", pause=0.7),
        ]},
        {"name": "solution", "label": "The solution", "lines": [
            line("warm", "built", "So we built Dark Matter, a free tool that measures the private money on Near.", pause=0.5),
            line("awe", "cantopen", "You can't open the box.", pause=0.3),
            line("firm", "scale", "But you can put it on a scale.", pause=0.6),
            line("warm", "cross", "All the money behind that private system sits in one account on Near. And that account is public. That's our scale.", pause=0.5),
        ]},
        {"name": "weigh", "label": "See it work", "lines": [
            line("turn", "watch", "So, watch this.", pause=0.5),
            line("warm", "click", "One click, and your browser reads it straight from Near."),
            line("firm", "noserver", "No login. Nothing to install.", pause=0.8),
            line("awe", "result", f"About {millions(n['snapshot_usd'])}. Live. Right now.", f"About ${usd} million. Live, right now.", pause=0.6),
            line("hush", "weight", "That's how much is inside the locked box.", pause=0.7),
        ]},
        {"name": "benefit", "label": "What you get", "lines": [
            line("ask", "get", "So what do you get?", pause=0.4),
            line("warm", "first", "First, you can check it yourself, any time, for free.", pause=0.45),
            line("warm", "second", "Second, you can see if Near is getting paid."),
            line("plain", "before", f"Until {month}, it earned {cash(n['bps_before'])} on every ten thousand dollars traded.",
                 f"Until {month}, it earned ${n['bps_before']} on every $10,000 traded."),
            line("wow", "after", f"Since then? About {words(now)} dollars. Almost double.", f"Since then: about ${now}. Almost double.", pause=0.5),
            line("firm", "tests", f"Third, {words(len(states))} public checks that could show we're wrong.",
                 f"Third, {len(states)} public checks that could show we're wrong."),
            line("plain", "states", f"{words(states.count('holding')).capitalize()} are fine. One is shaky. One isn't due yet.",
                 f"{states.count('holding')} are fine. 1 is shaky. 1 isn't due yet.", pause=0.6),
        ]},
        {"name": "honest", "label": "What we found", "lines": [
            line("plain", "tested", "We also tested a popular idea: that more trading now means more people using Near later.", pause=0.6),
            line("heavy", "verdict", "It barely does.", pause=0.5),
            line("firm", "page", "And we say so.", pause=0.7),
        ]},
        {"name": "maths", "label": "The five-year question", "lines": [
            line("ask", "carry", "Can Near cover its own costs by twenty thirty-one?", "Can NEAR cover its own costs by 2031?", pause=0.35),
            line("plain", "need", f"It hands out new coins every day, and that costs everyone who holds it. To cover that, trading has to grow at least {words(floor)} percent a year.",
                 f"It hands out new coins every day, and that costs everyone who holds it. To cover that, trading has to grow at least {floor}% a year."),
            line("wow", "lately", f"Over the last year, it grew {words(trend)}.", f"Over the last year, it grew {trend}%.", pause=0.4),
            line("warm", "possible", "So it's possible.", pause=0.4),
            line("firm", "promised", "But it's not promised.", pause=0.7),
        ]},
        {"name": "you", "label": "Your turn", "lines": [
            line("plea", "check", "So before you trust Near with your money, check it yourself.", pause=0.45),
            line("plea", "link", "The link is in this post.", pause=0.45),
            line("ask", "mind", "And tell us: what else would you want to check?", pause=1.6),
        ]},
    ]


def write_guide(script: list[dict]) -> str:
    out = [
        "# Demo video script",
        "",
        "Generated by `pipeline/demo_script.py` from the computed numbers. Do not edit it by hand.",
        "",
        "## Recording it in your own voice",
        "",
        "1. Read each take below aloud, in one go, into your phone or computer. Leave a clear breath between lines, so the",
        "   captions can find them. The note in brackets says how to say the line. Pauses matter more than volume.",
        f"   All {words(len(script))} takes together should last under 2 minutes 15 seconds, because X limits a standard account to 2 minutes 20.",
        "2. Save the takes in one folder, named after the take: "
        + ", ".join(f"`{i:02d}.m4a`" for i in range(1, 4)) + " and so on. Any common audio format works.",
        "3. Rebuild the video around your voice. The picture and captions follow your timing:",
        "",
        "```bash",
        "pip install numpy imageio-ffmpeg",
        "```",
        "",
        "```bash",
        "python pipeline/make_voice.py --recordings path/to/your/folder",
        "```",
        "",
        "```bash",
        "python pipeline/make_demo.py",
        "```",
        "",
    ]
    for i, take in enumerate(script, 1):
        out += [f"## Take {i:02d}: {take['label']}", ""]
        out += [f"- {entry['show']} *({MOODS[entry['mood']]['cue']})*" for entry in take["lines"]]
        out += [""]
    return "\n".join(out)


def load() -> list[dict]:
    return takes(read_json(DERIVED / "numbers.json"), read_json(DERIVED / "tests.json"))


def main() -> int:
    script = load()
    target = ROOT / "docs" / "DEMO_SCRIPT.md"
    target.write_text(write_guide(script), encoding="utf-8", newline="\n")
    spoken = sum(len(entry["say"].split()) for take in script for entry in take["lines"])
    print(f"{target.relative_to(ROOT)}: {len(script)} takes, {spoken} spoken words")
    return 0


if __name__ == "__main__":
    sys.exit(main())

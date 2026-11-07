"""The SHA-256 of every raw input, and one hash over the list that identifies the whole dataset.

    python pipeline/manifest.py write   after new data
    python pipeline/manifest.py check   stops if a raw file has changed
"""
from __future__ import annotations

import sys

from common import RAW, ROOT, STATIC, read_json, sha256_file, write_json

PATH = ROOT / "data" / "manifest.json"


def current() -> dict[str, str]:
    files = {}
    for folder in (RAW, STATIC):
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                files[path.relative_to(ROOT).as_posix()] = sha256_file(path)
    return files


def write() -> str:
    write_json(PATH, current())
    return sha256_file(PATH)


def check() -> int:
    if not PATH.exists():
        print("no manifest yet: run `python pipeline/manifest.py write`")
        return 1
    want, have = read_json(PATH), current()
    changed = sorted(k for k in set(want) | set(have) if want.get(k) != have.get(k))
    for name in changed[:10]:
        print("changed:", name)
    print("manifest", "OK" if not changed else f"differs in {len(changed)} file(s)", f"({len(want)} files)")
    return 1 if changed else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["write"]:
        print(write())
    else:
        sys.exit(check())

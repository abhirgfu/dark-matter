"""Write fixture.json for the VM test: the deploy token list, and the answers intents.near gave for it."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
args = json.loads((ROOT / "contract" / "init_args.json").read_text(encoding="utf-8"))
with open(ROOT / "data" / "raw" / "treasury_daily.jsonl", encoding="utf-8") as fh:
    days = [json.loads(line) for line in fh]
latest = max(days, key=lambda d: d["date"])
control = json.loads((ROOT / "data" / "raw" / "control.json").read_text(encoding="utf-8"))
fixture = {
    "treasury": args["treasury"],
    "tokens": args["tokens"],
    "balances": [latest["balances"].get(t, "0") for t in args["tokens"]],
    "keys": control["verifier_keys_now"],
    "date": latest["date"],
}
path = pathlib.Path(__file__).with_name("fixture.json")
path.write_text(json.dumps(fixture, indent=1) + "\n", encoding="utf-8", newline="\n")
print(path.name, len(fixture["tokens"]), "tokens from", fixture["date"])

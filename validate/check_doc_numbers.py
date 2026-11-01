"""Check that every decimal number and percentage in the written docs traces to docs/RESULTS.md,
or is a declared design constant (a planted value or pre-registered threshold).

Checks the README, plus any further paths listed one per line in validate/extra_docs.txt if present.
Run: python -m validate.check_doc_numbers
"""
import json
import re

from analysis.common import REGISTER_DIR, ROOT

# Numbers chosen before any result existed: planted values, thresholds, planning figures, sizes.
DESIGN = {
    "1.2", "0.4", "0.3", "0.5", "1.0", "2.0", "0.2", "0.735", "0.718", "0.262", "0.576", "0.6", "0.8", "0.7", "1.5", "2.5", "16.0",
    "0.03", "0.01", "0.15", "0.55", "0.05", "0.001", "0.10", "0.1", "1.96", "0.45", "0.9", "6.0", "22.0", "5.5", "5.0", "3.0", "73.4", "2.1", "0.00006",
    "12", "50", "95", "5", "15", "10", "25", "100", "55", "30", "60", "40", "80", "1.4", "0.513", "0.23", "0.057",
    "2.80", "2.8",
}
TOKEN = re.compile(r"(?<![\w.\-/`])[-+]?(\d+\.\d+|\d+(?=%))")


def registered_values():
    values = []
    for f in REGISTER_DIR.glob("*.json"):
        values += [x["value"] for x in json.loads(f.read_text()) if not isinstance(x["value"], str)]
    return values


def matches(token, values):
    d = len(token.split(".")[1]) if "." in token else 0
    target = float(token)
    return any(round(abs(v), d) == target for v in values)


def doc_paths():
    paths = ["README.md"]
    extra = ROOT / "validate" / "extra_docs.txt"
    if extra.exists():
        paths += [line.strip() for line in extra.read_text().splitlines() if line.strip()]
    return paths


def main():
    values = registered_values()
    problems = []
    paths = doc_paths()
    for path in paths:
        for token in TOKEN.findall((ROOT / path).read_text(encoding="utf-8")):
            if token not in DESIGN and not matches(token, values):
                problems.append((path, token))
    for p in sorted(set(problems)):
        print("UNTRACED", p)
    if problems:
        raise SystemExit(f"{len(set(problems))} untraced numbers")
    print(f"All numbers in {len(paths)} docs trace to RESULTS.md or to declared design constants.")


if __name__ == "__main__":
    main()

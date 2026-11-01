"""Shared paths and the results register used by all analysis code.

record() is how a number becomes "headline". It stores the value with the file and line that
produced it, so docs/RESULTS.md is generated from code and cannot drift from what actually ran.
"""
import datetime as dt
import inspect
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBSERVED = ROOT / "data" / "observed"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"
REGISTER_DIR = ROOT / "outputs" / "results"
SEED = 20261101  # same value as simulator.config.SEED; repeated so analysis never imports the simulator


class Register:
    """Collects (id, value, description, source location) and saves them to a JSON file."""

    def __init__(self, name: str, command: str):
        self.name, self.command = name, command
        self.items = []

    def record(self, key, value, description, unit=""):
        caller = inspect.stack()[1]
        self.items.append({
            "id": key,
            "value": float(value) if not isinstance(value, str) else value,
            "unit": unit,
            "description": description,
            "source": f"{Path(caller.filename).resolve().relative_to(ROOT).as_posix()}:{caller.lineno}",
            "command": self.command,
            "date": dt.date.today().isoformat(),
            "seed": SEED,
        })

    def save(self):
        REGISTER_DIR.mkdir(parents=True, exist_ok=True)
        (REGISTER_DIR / f"{self.name}.json").write_text(json.dumps(self.items, indent=1))

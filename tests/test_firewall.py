"""Analysis must never touch the planted truth. Two layers: a text scan and a runtime trap.

The runtime trap uses Python's audit hook, which sees Python file opens. DuckDB reads files itself and
is invisible to that hook, which is why sql/ is covered by the text scan.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = re.compile(r"data[/\\]+truth|truth\.json|[\"']truth[\"']|TRUTH\b")
ANALYSIS_FILES = [p for folder in ("analysis", "sql") for p in (ROOT / folder).iterdir() if p.suffix in {".py", ".sql"}]

TRAP = """
import sys, runpy
def hook(event, args):
    if event == "open" and args and "truth" in str(args[0]).replace("\\\\", "/").split("/")[-2:][0]:
        raise PermissionError(f"FIREWALL: analysis opened {args[0]}")
sys.addaudithook(hook)
"""


@pytest.mark.parametrize("path", ANALYSIS_FILES, ids=lambda p: p.name)
def test_no_analysis_file_mentions_the_truth_folder(path):
    assert not FORBIDDEN.search(path.read_text()), f"{path} refers to the truth folder"


def test_analysis_does_not_import_the_simulator_or_validation():
    for path in ANALYSIS_FILES:
        if path.suffix == ".py":
            assert not re.search(r"^\s*(from|import)\s+(simulator|validate)\b", path.read_text(), re.M), path


def run_trapped(code):
    return subprocess.run([sys.executable, "-W", "ignore", "-c", TRAP + code], cwd=ROOT, capture_output=True, text=True)


def test_the_trap_really_catches_a_violation(tmp_path):
    """If this failed, the runtime test below would prove nothing."""
    truth = tmp_path / "truth"
    truth.mkdir()
    (truth / "x.json").write_text("{}")
    result = run_trapped(f"open(r'{truth / 'x.json'}')")
    assert result.returncode != 0 and "FIREWALL" in result.stderr


def test_pilot_analysis_runs_without_opening_truth():
    if not (ROOT / "outputs" / "tables" / "store_week_panel.csv").exists():
        pytest.skip("generate the outputs first")
    result = run_trapped("import analysis.run_pilot as m; m.main()")
    assert result.returncode == 0, result.stderr[-800:]


def test_scanner_would_flag_a_bad_file():
    assert FORBIDDEN.search("pd.read_json('data/truth/truth.json')")
    assert not FORBIDDEN.search("Run all methods without using any truth.")

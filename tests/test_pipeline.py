import hashlib
import subprocess
import sys
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parents[1] / "src"
SESSIONS = 300


def run(script, *args, check=True):
    return subprocess.run([sys.executable, str(SRC / script),
                           *[str(a) for a in args]],
                          capture_output=True, text=True, check=check)


def build(root, name):
    base, final = root / f"{name}_base", root / name
    run("master_data.py", "--sessions", SESSIONS, "--out", base)
    run("journeys.py", "--sessions", SESSIONS, "--out", base)
    run("anomalies.py", "--src", base, "--out", final)
    return final


def hashes(folder):
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(folder.glob("*.csv"))}


def test_same_seed_gives_identical_files(tmp_path):
    assert hashes(build(tmp_path, "a")) == hashes(build(tmp_path, "b"))


def test_validation_passes_on_a_clean_build(tmp_path):
    data = build(tmp_path, "a")
    result = run("validate.py", "--data", data,
                 "--report-dir", tmp_path / "rep", check=False)
    assert result.returncode == 0, result.stdout


def test_validation_catches_a_broken_order_total(tmp_path):
    data = build(tmp_path, "a")
    orders = pd.read_csv(data / "orders.csv", dtype=str, keep_default_na=False)
    orders.loc[0, "total_amount"] = "1.00"
    orders.to_csv(data / "orders.csv", index=False, lineterminator="\n")
    result = run("validate.py", "--data", data,
                 "--report-dir", tmp_path / "rep", check=False)
    assert result.returncode != 0
    assert "order total" in result.stdout


def test_ground_truth_stays_out_of_the_input_tables(tmp_path):
    data = build(tmp_path, "a")
    for name in ("sessions", "journey_events", "journey_outcomes"):
        columns = pd.read_csv(data / f"{name}.csv", nrows=1).columns
        assert "issue_type" not in columns and "is_bot" not in columns
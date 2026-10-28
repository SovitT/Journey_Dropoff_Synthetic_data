import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

from common import SEED

SRC = Path(__file__).resolve().parent
WORK = Path("data/_work")          # scratch space, ignored by git


def run(script, *args):
    text = " ".join(str(a) for a in args)
    print(f"\n>> {script} {text}", flush=True)
    subprocess.run([sys.executable, str(SRC / script),
                    *[str(a) for a in args]], check=True)


def build(sessions, base, final):
    shutil.rmtree(base, ignore_errors=True)
    shutil.rmtree(final, ignore_errors=True)
    run("master_data.py", "--sessions", sessions, "--out", base)
    run("journeys.py", "--sessions", sessions, "--out", base)
    run("anomalies.py", "--src", base, "--out", final)


def fingerprint(folder):
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(Path(folder).glob("*.csv"))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=int, default=1000)
    parser.add_argument("--out", default="data/starter")
    parser.add_argument("--report-dir", default=None)
    parser.add_argument("--skip-repro", action="store_true",
                        help="skip the second build (saves time on 100k)")
    args = parser.parse_args()
    out = Path(args.out)
    reports = Path(args.report_dir or f"reports/{out.name}")
    reports.mkdir(parents=True, exist_ok=True)
    scratch = [WORK / f"{out.name}_base", WORK / f"{out.name}_base2",
               WORK / f"{out.name}_again"]

    build(args.sessions, scratch[0], out)
    run("validate.py", "--data", out, "--report-dir", reports)
    run("analyze.py", "--data", out, "--report-dir", reports)

    same = True
    if not args.skip_repro:
        build(args.sessions, scratch[1], scratch[2])
        first, second = fingerprint(out), fingerprint(scratch[2])
        same = first == second
        lines = ["# Reproducibility", "",
                 f"Seed {SEED}, {args.sessions:,} sessions. The whole build "
                 "was run twice and every file was hashed (SHA-256, first "
                 "16 characters shown).", "",
                 "| File | Run 1 | Run 2 | Same |", "|---|---|---|---|"]
        for name in first:
            a, b = first[name][:16], second.get(name, "missing")[:16]
            lines.append(f"| {name} | {a} | {b} | "
                         f"{'yes' if a == b else 'NO'} |")
        lines += ["", "**Result: " + ("identical" if same else "DIFFERENT")
                  + ".**", ""]
        (reports / "reproducibility.md").write_text("\n".join(lines),
                                                    encoding="utf-8")
        print("\nReproducibility:", "identical" if same else "DIFFERENT")

    for folder in scratch:
        shutil.rmtree(folder, ignore_errors=True)
    if WORK.exists() and not any(WORK.iterdir()):
        WORK.rmdir()
    sys.exit(0 if same else 1)


if __name__ == "__main__":
    main()
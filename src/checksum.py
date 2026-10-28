"""Prints a short fingerprint (hash) of every CSV in a folder."""
import hashlib
import sys
from pathlib import Path

folder = Path(sys.argv[1])
for f in sorted(folder.glob("*.csv")):
    print(f.name, hashlib.sha256(f.read_bytes()).hexdigest()[:16])
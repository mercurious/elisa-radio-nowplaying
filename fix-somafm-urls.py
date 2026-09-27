#!/usr/bin/env python3
"""Rewrite Elisa's SomaFM radio URLs so libVLC can read ICY now-playing metadata.

- https:// -> http://  (VLC 3's HTTPS access module drops ICY metadata)
- "-256.mp3" style suffixes -> "-256-mp3" (the .mp3 variants 404 on SomaFM)

Backs up the database first. Quit Elisa before running. Safe to re-run.
"""
import datetime
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

DB = Path.home() / ".local/share/elisa/elisaDatabase.db"
BACKUP = DB.with_name(f"{DB.name}.bak-{datetime.date.today().isoformat()}")

if subprocess.run(["pgrep", "-x", "elisa"], capture_output=True).returncode == 0:
    sys.exit("Elisa is running; quit it first so it doesn't overwrite the change.")

if not BACKUP.exists():
    shutil.copy2(DB, BACKUP)
    print(f"Backup: {BACKUP}")

con = sqlite3.connect(DB)
rows = con.execute(
    "SELECT ID, HttpAddress FROM Radios WHERE HttpAddress LIKE '%somafm.com/%'"
).fetchall()
for rid, url in rows:
    new = re.sub(r"^https://", "http://", url)
    new = re.sub(r"-(\d+)\.mp3$", r"-\1-mp3", new)
    if new != url:
        con.execute("UPDATE Radios SET HttpAddress = ? WHERE ID = ?", (new, rid))
        print(f"{rid:>3}: {url}\n     -> {new}")
con.commit()
con.close()

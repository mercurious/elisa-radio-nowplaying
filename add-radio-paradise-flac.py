#!/usr/bin/env python3
"""Add Radio Paradise's lossless FLAC channels to Elisa's radio list.

Uses the "flacm" streams: FLAC 16-bit/44.1 kHz *with* ICY now-playing metadata
(the plain "flac" streams carry no track info). They must be http:// because
VLC 3 drops ICY metadata over HTTPS.

Backs up the database first. Quit Elisa before running. Safe to re-run.
"""
import datetime
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

DB = Path.home() / ".local/share/elisa/elisaDatabase.db"
BACKUP = DB.with_name(f"{DB.name}.bak-{datetime.date.today().isoformat()}")

LOGO = "https://vsh-smedia.radioparadise.com/uploads/RP_Logo_Flat_HCR_Green_1_18a033c355.png"
STATIONS = [
    ("flacm", "Radio Paradise - Main Mix (FLAC)"),
    ("mellow-flacm", "Radio Paradise - Mellow Mix (FLAC)"),
    ("rock-flacm", "Radio Paradise - Rock Mix (FLAC)"),
    ("global-flacm", "Radio Paradise - Global Mix (FLAC)"),
]

if subprocess.run(["pgrep", "-x", "elisa"], capture_output=True).returncode == 0:
    sys.exit("Elisa is running; quit it first so it doesn't overwrite the change.")

if not BACKUP.exists():
    shutil.copy2(DB, BACKUP)
    print(f"Backup: {BACKUP}")

con = sqlite3.connect(DB)
for path, title in STATIONS:
    url = f"http://stream.radioparadise.com/{path}"
    cur = con.execute(
        "INSERT OR IGNORE INTO Radios (HttpAddress, ImageAddress, Title, Comment) VALUES (?, ?, ?, ?)",
        (url, LOGO, title, "Lossless FLAC 16-bit/44.1 kHz"),
    )
    print(f"{'added' if cur.rowcount else 'exists'}: {title}  {url}")
con.commit()
con.close()

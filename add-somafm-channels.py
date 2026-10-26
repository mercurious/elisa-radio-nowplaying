#!/usr/bin/env python3
"""Add every SomaFM channel to Elisa's radio list.

Reads the live channel list (somafm.com/channels.json) and each channel's MP3
playlist, then adds the ones Elisa doesn't have yet as "SomaFM - <title>". Stream
URLs use the plain-http form that libVLC 3 needs for ICY now-playing metadata
(see fix-somafm-urls.py). Channels already in the list are left alone, except ones saved as .pls links,
which are switched to the direct stream and the channel's real title.

Backs up the database first. Quit Elisa before running. Safe to re-run.
Pass --dry-run to just show what would be added.
"""
import datetime
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path

DB = Path.home() / ".local/share/elisa/elisaDatabase.db"
BACKUP = DB.with_name(f"{DB.name}.bak-{datetime.date.today().isoformat()}")
dry_run = "--dry-run" in sys.argv[1:]


def fetch(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode()


def stream_url(pls_url):
    """First stream in a .pls, as ice1 over http with the working '-NNN-mp3' form."""
    m = re.search(r"^File1=(\S+)$", fetch(pls_url), re.M)
    if not m:
        return None
    url = re.sub(r"^https://ice\d+\.", "http://ice1.", m.group(1))
    return re.sub(r"-(\d+)\.mp3$", r"-\1-mp3", url)


if not dry_run and subprocess.run(["pgrep", "-x", "elisa"], capture_output=True).returncode == 0:
    sys.exit("Elisa is running; quit it first so it doesn't overwrite the change.")

channels = json.loads(fetch("https://somafm.com/channels.json"))["channels"]

con = sqlite3.connect(DB)
existing = con.execute("SELECT ID, HttpAddress FROM Radios WHERE HttpAddress LIKE '%somafm.com/%'").fetchall()

if not dry_run and not BACKUP.exists():
    shutil.copy2(DB, BACKUP)
    print(f"Backup: {BACKUP}")

for ch in channels:
    cid, title = ch["id"], "SomaFM - " + re.sub(r"^SomaFM ", "", ch["title"])
    # Match "/<id>.pls", "/<id>-256-mp3", "/<id>256.pls" etc., but not "/<id>2..." (other channels).
    found = [(rid, a) for rid, a in existing if re.search(rf"somafm\.com/{re.escape(cid)}(?![a-z0-9])", a)]
    if found and not found[0][1].endswith(".pls"):
        print(f"exists: {title}")
        continue
    pls = next((p["url"] for p in ch["playlists"] if p["format"] == "mp3"), None)
    url = stream_url(pls) if pls else None
    if not url:
        print(f"skipped (no MP3 stream): {title}")
        continue
    if found:  # saved as a .pls link: switch to the direct stream and the canonical title
        con.execute(
            "UPDATE Radios SET HttpAddress = ?, Title = ? WHERE ID = ?", (url, title, found[0][0])
        )
        print(f"fixed: {found[0][1]}  ->  {title}  {url}")
        continue
    cur = con.execute(
        "INSERT OR IGNORE INTO Radios (HttpAddress, ImageAddress, Title, Comment) VALUES (?, ?, ?, ?)",
        (url, ch.get("largeimage") or ch["image"], title, ch["description"]),
    )
    print(f"{'added' if cur.rowcount else 'exists'}: {title}  {url}")

if dry_run:
    con.rollback()
else:
    con.commit()
con.close()

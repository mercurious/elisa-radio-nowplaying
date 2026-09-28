#!/usr/bin/env python3
"""Point Elisa's WNYC entries at the local pacing relay, and drop the broken AAC one.

WNYC's edge CDN delivers audio in bursts that VLC 3's jitter buffer can't absorb,
so the MP3 stream stutters. wnyc-relay/ fixes that by re-serving it at a steady
pace. The AAC stream is a separate, unfixable problem: it uses implicit HE-AACv2
(SBR+PS) signaling that both of VLC 3's AAC decoders (faad, avcodec) mishandle,
permanently desyncing the playback clock -- no audio ever comes out. There's no
local relay fix for that (ffmpeg decodes it fine, but VLC can't), so this script
just removes it.

Backs up the database first. Quit Elisa before running. Safe to re-run; also
moves stations added with the direct fm939.wnyc.org URL to the relay.
"""
import datetime
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

DB = Path.home() / ".local/share/elisa/elisaDatabase.db"
BACKUP = DB.with_name(f"{DB.name}.bak-{datetime.date.today().isoformat()}")

STATIONS = [
    ("wnycfm", "https://fm939.wnyc.org/wnycfm"),
    ("wnycam", "https://am820.wnyc.org/wnycam"),
]
BROKEN_AAC_URLS = [
    "https://fm939.wnyc.org/wnycfm.aac",
    "https://am820.wnyc.org/wnycam.aac",
]

if subprocess.run(["pgrep", "-x", "elisa"], capture_output=True).returncode == 0:
    sys.exit("Elisa is running; quit it first so it doesn't overwrite the change.")

if not BACKUP.exists():
    shutil.copy2(DB, BACKUP)
    print(f"Backup: {BACKUP}")

con = sqlite3.connect(DB)
for path, direct_url in STATIONS:
    url = f"http://127.0.0.1:8395/{path}"
    cur = con.execute(
        "UPDATE Radios SET HttpAddress = ? WHERE HttpAddress = ?",
        (url, direct_url),
    )
    if cur.rowcount:
        print(f"moved to relay: {direct_url}  ->  {url}")

for url in BROKEN_AAC_URLS:
    cur = con.execute("DELETE FROM Radios WHERE HttpAddress = ?", (url,))
    if cur.rowcount:
        print(f"removed (unfixable in VLC 3): {url}")

con.commit()
con.close()

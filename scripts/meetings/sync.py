#!/usr/bin/env python3
"""Sync meeting materials from psbma.org into docs/meetings/.

STATUS: skeleton. The decision logic (which meetings need work, folder names,
retry window) is real. The scraping and download steps are TODO and raise
NotImplementedError. See plans/0001-generate-meeting-pages.md.

Design rules (also in CLAUDE.md):
  * The filesystem is the state. meta.json is written last, after every file
    for the meeting is saved.
  * URLs come from the raw page HTML, whole. Never from a summary.
  * A failure on one meeting must not stop the others.
"""
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import build_site

REPO = Path(__file__).resolve().parents[2]
MEETINGS_DIR = REPO / "docs" / "meetings"
LISTING_URL = "https://www.psbma.org/district/school-committee/meeting-materials"
RETRY_DAYS = 30  # keep retrying incomplete meetings this long after the meeting date


@dataclass
class Meeting:
    event_id: str          # CivicClerk event id, e.g. "16516"
    day: date
    time: str              # "18:00" or ""
    body: str              # "School Committee", "Finance and Capital Projects Subcommittee", ...
    title: str
    recording_url: str = ""    # as found on the page (YouTube, Zoom, or share.google redirect)
    agenda_url: str = ""       # CivicClerk agenda link
    extra: dict = field(default_factory=dict)


def today_eastern():
    return datetime.now(ZoneInfo("America/New_York")).date()


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def meeting_dir(m):
    return MEETINGS_DIR / f"{m.day.isoformat()}-{slugify(m.body)}"


def load_meta(mdir):
    p = mdir / "meta.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None  # treat a corrupt meta.json as "not done"


def needs_work(m, meta, today):
    if m.day > today:
        return False  # upcoming meeting
    if meta is None:
        return True
    if meta.get("status") == "complete":
        return False
    return (today - m.day) <= timedelta(days=RETRY_DAYS)


def fetch_listing():
    """TODO: GET LISTING_URL with requests, parse the raw HTML with BeautifulSoup,
    return list[Meeting]. Keep hrefs exactly as found (no summarizing)."""
    raise NotImplementedError("scraper not written yet")


def process_meeting(m, mdir):
    """TODO. For one meeting:
      1. Resolve the recording link (follow share.google redirects). YouTube: yt-dlp
         auto-subs to transcript.txt. Zoom: try the play page transcript, else record
         status 'no-transcript'.
      2. Download the agenda PDF to agenda.pdf.
      3. Download the supporting documents and save the PDFs inside the packet to
         agenda-packet/. Do NOT save the combined package PDF.
      4. Write meta.json LAST with status complete / no-transcript /
         recording-unavailable / incomplete (see build_site.py for the fields).
    """
    raise NotImplementedError("per-meeting download not written yet")


def main():
    dry = "--dry-run" in sys.argv
    today = today_eastern()
    try:
        meetings = fetch_listing()
    except NotImplementedError as e:
        print(f"sync skipped: {e}", file=sys.stderr)
        build_site.main([])
        return 2

    todo = [m for m in meetings if needs_work(m, load_meta(meeting_dir(m)), today)]
    print(f"{len(meetings)} meetings on page, {len(todo)} need work")
    failures = 0
    for m in todo:
        mdir = meeting_dir(m)
        print(f"- {m.day} {m.body}: {'would process' if dry else 'processing'}")
        if dry:
            continue
        try:
            mdir.mkdir(parents=True, exist_ok=True)
            process_meeting(m, mdir)
        except Exception as e:  # keep going; the command logs this to ops/issues.md
            failures += 1
            print(f"FAILED {m.day} {m.body}: {e!r}", file=sys.stderr)

    build_site.main([])
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

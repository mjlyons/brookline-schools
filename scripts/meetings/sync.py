#!/usr/bin/env python3
"""Sync meeting materials from psbma.org into docs/meetings/.

See plans/0001-generate-meeting-pages.md. Flags: --dry-run (list only).

Design rules (also in CLAUDE.md):
  * The filesystem is the state. meta.json is written last, after every file
    for the meeting is saved.
  * URLs come from the raw page HTML, whole. Never from a summary.
  * A failure on one meeting must not stop the others.
"""
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

import build_site

REPO = Path(__file__).resolve().parents[2]
MEETINGS_DIR = REPO / "docs" / "meetings"
LISTING_URL = "https://www.psbma.org/district/school-committee/meeting-materials"
RETRY_DAYS = 30  # keep retrying incomplete meetings this long after the meeting date
API = "https://brooklinema.api.civicclerk.com/v1/Meetings/GetMeetingFileStream(fileId={},plainText=false)"
HEADING_RE = re.compile(r"^\s*([A-Z][a-z]+ \d{1,2}, \d{4})\s*[-\u2013\u2014]\s*(.+)$")
CC_RE = re.compile(r"civicclerk\.com/event/(\d+)/files/(agenda|attachment)/(\d+)")
HTTP = requests.Session()
HTTP.headers["User-Agent"] = "brookline-schools-archive (+https://github.com/mjlyons/brookline-schools)"


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
    suffix = f"-{m.event_id}" if m.extra.get("collision") else ""
    return MEETINGS_DIR / f"{m.day.isoformat()}-{slugify(m.body)}{suffix}"


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


def parse_heading(text):
    """'September 30, 2026 - School Committee Meeting - 6:00 p.m. - Town Hall' ->
    (date, body, "18:00")."""
    text = text.replace("\xa0", " ")
    mo = HEADING_RE.match(text)
    if not mo:
        return None
    day = datetime.strptime(mo.group(1), "%B %d, %Y").date()
    parts = [p.strip() for p in re.split(r"\s+[-\u2013\u2014]\s+", mo.group(2)) if p.strip()]
    clock = ""
    body_parts = []
    for p in parts:
        tm = re.match(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?", p, re.I)
        if tm and not clock:
            h = int(tm.group(1)) % 12 + (12 if tm.group(3).lower() == "p" else 0)
            clock = f"{h:02d}:{tm.group(2) or '00'}"
        elif not clock:
            body_parts.append(p)  # everything before the time is the body
    return day, " ".join(body_parts) or parts[0], clock


def recording_kind(url):
    if "youtu" in url:
        return "youtube"
    if "zoom" in url:
        return "zoom"
    return "other"


def fetch_listing():
    """Parse the raw HTML of the materials page. Hrefs are kept exactly as found."""
    r = HTTP.get(LISTING_URL, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    meetings = []
    for h in soup.find_all("h3"):
        parsed = parse_heading(h.get_text(" ", strip=True))
        ul = h.find_next_sibling("ul")
        if not parsed or ul is None:
            continue
        day, body, clock = parsed
        m = Meeting(event_id="", day=day, time=clock, body=body,
                    title=f"{body} ({day.strftime('%B')} {day.day}, {day.year})")
        m.extra["packet"] = []   # (file_id, label)
        seen = set()
        for a in ul.find_all("a", href=True):
            href, label = a["href"].strip(), a.get_text(" ", strip=True)
            cc = CC_RE.search(href)
            if cc:
                m.event_id = m.event_id or cc.group(1)
                kind, fid = cc.group(2), cc.group(3)
                if kind == "agenda":
                    m.agenda_url = m.agenda_url or href
                    m.extra["agenda_id"] = m.extra.get("agenda_id") or fid
                elif fid not in seen:
                    seen.add(fid)
                    m.extra["packet"].append((fid, label))
            elif re.search(r"youtu|zoom|share\.google|brooklineinteractive", href) and not m.recording_url:
                m.recording_url = href
        meetings.append(m)
    by_key = {}
    for m in meetings:
        by_key.setdefault((m.day, slugify(m.body)), []).append(m)
    for group in by_key.values():
        if len(group) > 1:
            for m in group:
                m.extra["collision"] = True
    return meetings


def download_pdf(file_id, dest):
    r = HTTP.get(API.format(file_id), timeout=120)
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise ValueError(f"file {file_id} is not a PDF")
    dest.write_bytes(r.content)


def resolve_recording(url):
    """Follow redirects (share.google) and return (kind, final_url). Raises on failure."""
    if "share.google" in url:
        r = HTTP.get(url, timeout=60, allow_redirects=True)
        r.raise_for_status()
        url = r.url
    return recording_kind(url), url


def vtt_to_text(vtt):
    lines, prev = [], ""
    for line in vtt.splitlines():
        line = re.sub(r"<[^>]+>", "", line).strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or "-->" in line:
            continue
        if line != prev:
            lines.append(line)
        prev = line
    return "\n".join(lines) + "\n"


def youtube_transcript(url, dest):
    """Return True if a transcript was written. Uses yt-dlp auto subs."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", "en",
             "--sub-format", "vtt", "-o", f"{tmp}/s.%(ext)s", url],
            capture_output=True, text=True, timeout=300)
        vtts = sorted(Path(tmp).glob("*.vtt"))
        if not vtts:
            return False
        dest.write_text(vtt_to_text(vtts[0].read_text(encoding="utf-8")), encoding="utf-8")
        return True


def process_meeting(m, mdir):
    """Download everything for one meeting, then write meta.json last."""
    problems = []
    files = {"transcript": None, "agenda": None, "agenda_packet": []}

    if m.extra.get("agenda_id"):
        try:
            download_pdf(m.extra["agenda_id"], mdir / "agenda.pdf")
            files["agenda"] = "agenda.pdf"
        except Exception as e:
            problems.append(f"agenda: {e!r}")

    (mdir / "agenda-packet").mkdir(exist_ok=True)
    for i, (fid, label) in enumerate(m.extra["packet"], 1):
        rel = f"agenda-packet/{i:02d}-{slugify(label)[:60] or fid}.pdf"
        try:
            download_pdf(fid, mdir / rel)
            files["agenda_packet"].append(rel)
        except Exception as e:
            problems.append(f"packet {fid} ({label}): {e!r}")
    if not files["agenda_packet"]:
        try:
            (mdir / "agenda-packet").rmdir()
        except OSError:
            pass

    recording = None
    status = "recording-unavailable"
    if m.recording_url:
        try:
            kind, url = resolve_recording(m.recording_url)
            recording = {"kind": kind, "url": url}
            status = "no-transcript"
            if kind == "youtube":
                if youtube_transcript(url, mdir / "transcript.txt"):
                    files["transcript"] = "transcript.txt"
                else:
                    problems.append("youtube transcript not downloaded")
            # Zoom play pages do not expose a transcript in their HTML; stays no-transcript.
        except Exception as e:
            recording = {"kind": recording_kind(m.recording_url), "url": m.recording_url}
            status = "incomplete"
            problems.append(f"recording {m.recording_url}: {e!r}")
    if files["transcript"] and files["agenda"] and not problems:
        status = "complete"
    elif problems and status in ("recording-unavailable", "no-transcript"):
        status = "incomplete" if (not files["agenda"] or recording) else status

    meta = {
        "title": m.title, "body": m.body, "date": m.day.isoformat(), "time": m.time,
        "status": status, "recording": recording, "files": files,
        "event_id": m.event_id,
    }
    if m.agenda_url:
        meta["agenda_package_source_url"] = m.agenda_url
    (mdir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    for p in problems:
        print(f"  note: {p}", file=sys.stderr)


def main():
    dry = "--dry-run" in sys.argv
    today = today_eastern()
    meetings = fetch_listing()

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

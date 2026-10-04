#!/usr/bin/env python3
"""Rebuild the generated HTML under docs/meetings/ from each meeting's meta.json.

Deterministic and idempotent: the same meta.json files always produce the same
HTML. Safe to run any number of times. No timestamps are written.

meta.json fields used:
  title, body, date (YYYY-MM-DD), time (optional, HH:MM), status,
  recording: {"kind": "youtube" | "zoom", "url": "..."} or null,
  files: {"transcript": "transcript.txt" | null,
          "agenda": "agenda.pdf" | null,
          "agenda_packet": ["agenda-packet/01-name.pdf", ...]},
  agenda_package_source_url: optional external link to the combined package
"""
import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

CSS = """
body{font:16px/1.5 system-ui,sans-serif;max-width:42rem;margin:2rem auto;padding:0 1rem;color:#1a1a1a;background:#fff}
a{color:#0b5cad}
h1{font-size:1.5rem;line-height:1.25}
ul{padding-left:1.25rem}
li{margin:.35rem 0}
.meta{color:#555}
.note{color:#555;font-style:italic}
@media (prefers-color-scheme:dark){body{color:#e8e8e8;background:#121212}a{color:#7ab7ff}.meta,.note{color:#aaa}}
"""

STATUS_NOTES = {
    "recording-unavailable": "No recording was available when this page was last built.",
    "no-transcript": "A recording exists but no transcript could be downloaded.",
    "incomplete": "Some materials for this meeting have not been collected yet.",
}


def esc(s):
    return html.escape(str(s), quote=True)


def pretty_date(iso):
    d = date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def page(title, body):
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n"
        f"{body}\n</body>\n</html>\n"
    )


def pdf_label(rel):
    stem = Path(rel).stem
    stem = re.sub(r"^\d+[-_ ]*", "", stem)
    return stem.replace("-", " ").replace("_", " ").strip() or Path(rel).name


def load_meetings(meetings_dir):
    meetings = []
    for mdir in sorted(p for p in meetings_dir.iterdir() if p.is_dir()):
        meta_path = mdir / "meta.json"
        if not meta_path.exists():
            print(f"skip {mdir.name}: no meta.json (incomplete run)", file=sys.stderr)
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            date.fromisoformat(meta["date"])
            meta["title"]
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            print(f"skip {mdir.name}: bad meta.json ({e!r})", file=sys.stderr)
            continue
        meetings.append((mdir, meta))
    # Newest first. Ties broken by time, then directory name, so output is stable.
    meetings.sort(key=lambda m: (m[1]["date"], m[1].get("time", ""), m[0].name), reverse=True)
    return meetings


def linked_file(mdir, rel):
    """Return rel if the file exists, else None (and warn). Avoids dead links."""
    if not rel:
        return None
    if (mdir / rel).is_file():
        return rel
    print(f"warn {mdir.name}: listed file missing: {rel}", file=sys.stderr)
    return None


def meeting_page(mdir, meta):
    files = meta.get("files") or {}
    rec = meta.get("recording") or None
    when = pretty_date(meta["date"])
    if meta.get("time"):
        when += f" at {esc(meta['time'])}"

    parts = [f"<p><a href=\"../index.html\">All meetings</a></p>", f"<h1>{esc(meta['title'])}</h1>"]
    sub = [when]
    if meta.get("body"):
        sub.append(esc(meta["body"]))
    parts.append(f"<p class=\"meta\">{' | '.join(sub)}</p>")

    items = []
    if rec and rec.get("url"):
        kind = {"youtube": "YouTube", "zoom": "Zoom"}.get(rec.get("kind"), "link")
        items.append(f"<li><a href=\"{esc(rec['url'])}\">Recording ({kind})</a></li>")
    else:
        items.append('<li class="note">Recording not available</li>')

    transcript = linked_file(mdir, files.get("transcript"))
    if transcript:
        items.append(f"<li><a href=\"{esc(transcript)}\">Transcript</a></li>")
    else:
        items.append('<li class="note">Transcript not available</li>')

    agenda = linked_file(mdir, files.get("agenda"))
    if agenda:
        items.append(f"<li><a href=\"{esc(agenda)}\">Agenda (PDF)</a></li>")
    else:
        items.append('<li class="note">Agenda not available</li>')
    parts.append("<ul>\n" + "\n".join(items) + "\n</ul>")

    packet = [p for p in (linked_file(mdir, r) for r in files.get("agenda_packet") or []) if p]
    if packet or meta.get("agenda_package_source_url"):
        parts.append("<h2>Agenda package</h2>")
        lis = [f"<li><a href=\"{esc(p)}\">{esc(pdf_label(p))}</a></li>" for p in packet]
        if meta.get("agenda_package_source_url"):
            lis.append(
                f"<li><a href=\"{esc(meta['agenda_package_source_url'])}\">"
                "Original combined package (district site)</a></li>"
            )
        parts.append("<ul>\n" + "\n".join(lis) + "\n</ul>")

    note = STATUS_NOTES.get(meta.get("status"))
    if note:
        parts.append(f"<p class=\"note\">{esc(note)}</p>")
    return page(meta["title"], "\n".join(parts))


def index_page(meetings):
    lis = [
        f"<li><a href=\"{esc(mdir.name)}/index.html\">{esc(pretty_date(meta['date']))}: {esc(meta['title'])}</a></li>"
        for mdir, meta in meetings
    ]
    if lis:
        listing = "<ul>\n" + "\n".join(lis) + "\n</ul>"
    else:
        listing = '<p class="note">No meetings yet.</p>'
    body = "<p><a href=\"../index.html\">Home</a></p>\n<h1>Meetings</h1>\n" + listing
    return page("Meetings", body)


def write_if_changed(path, text):
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--docs", default=None, help="path to the docs/ directory (default: <repo>/docs)")
    args = ap.parse_args(argv)
    docs = Path(args.docs) if args.docs else Path(__file__).resolve().parents[2] / "docs"
    meetings_dir = docs / "meetings"
    meetings_dir.mkdir(parents=True, exist_ok=True)

    meetings = load_meetings(meetings_dir)
    changed = 0
    for mdir, meta in meetings:
        changed += write_if_changed(mdir / "index.html", meeting_page(mdir, meta))
    changed += write_if_changed(meetings_dir / "index.html", index_page(meetings))
    print(f"built {len(meetings)} meeting page(s), {changed} file(s) changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

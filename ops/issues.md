# Issues log

Not published (lives outside `docs/`). Newest first. Add an entry whenever a sync run or setup step hits a problem, even if it was worked around.

Format: `## YYYY-MM-DD: short title`, then what happened, impact, and status (open / resolved + how).

## 2026-10-04: Zoom share link truncated by page summary
- What: A summarizing fetch of the materials page returned a Zoom share URL missing its tail. The real link ends `...Pi1P8_8.XN5IidwPJVoPir7v?startTime=...`. The truncated link showed "recording does not exist".
- Impact: Looked like a dead recording but was a bad URL.
- Status: Resolved in design. Scripts must read hrefs from raw HTML and keep them whole. Never take URLs from a summary. Follow redirects (`/rec/share/` goes to `/rec/play/`).

## 2026-10-04: Fetch tool refused on zoomgov.com
- What: WebFetch returned ROBOTS_DISALLOWED for the Zoom share URL.
- Impact: Could not inspect the Zoom page from the fetch tool.
- Status: Open. Check the page in a real browser, or from the sync script once the network allowlist is set.

## 2026-10-04: Cloud sandbox shell blocked from needed hosts
- What: curl got `403 CONNECT tunnel failed` for www.psbma.org, share.google, and brooklinema.zoomgov.com (egress proxy, organization policy).
- Impact: The sync script cannot reach the materials page, Zoom, or share.google redirects.
- Status: Resolved 2026-10-04. After the allowlist change, curl returned 200 for psbma.org (materials page), civicclerk, zoomgov, share.google and youtube.com. googlevideo.com and i.ytimg.com roots returned 404 (reachable, not blocked by the proxy). Real downloads are untested.

## 2026-10-04: sync.py scraper not written
- What: `python scripts/meetings/sync.py` prints "sync skipped: scraper not written yet" and changes nothing.
- Impact: /sync-meetings cannot fetch any meetings yet.
- Status: Open. Build steps 1 to 6 in plans/0001-generate-meeting-pages.md.

## 2026-10-04: Zoom transcript availability unknown
- What: Not yet confirmed whether Zoom share pages offer a transcript or download.
- Impact: Zoom meetings may end up with a recording link but no transcript.
- Status: Open. Check a real Zoom play page (the DEIJ 2026-09-28 recording loads for the user).

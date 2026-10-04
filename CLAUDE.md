# brookline-schools

Archive and analysis workspace for Brookline Public Schools (PSBMA). The first feature is a daily sync of meeting materials from https://www.psbma.org/district/school-committee/meeting-materials. More sources and analysis will be added later.

The published site is `docs/` (GitHub Pages, deploy from branch `main`, folder `/docs`). Every push to `main` publishes.

## Layout

- `docs/` is published. Never put drafts or private notes here.
- `docs/meetings/<YYYY-MM-DD>-<body-slug>/` holds one meeting: `meta.json`, `index.html`, `transcript.txt`, `agenda.pdf`, and `agenda-packet/*.pdf`.
- `docs/meetings/index.html` is the meeting list, newest first, date and title only.
- `scripts/meetings/` holds the deterministic Python helpers. Put new sources in their own `scripts/<source>/` folder with their own command.
- `analysis/` is the user's working area. The sync never reads, writes, or deletes anything there.
- `ops/issues.md` is the issues log. It is not published.
- `plans/` holds numbered plan files. Update the relevant plan when scope or status changes.

## Sync rules (`/sync-meetings`)

- The filesystem is the state. Safe to run daily, any number of times.
- Consider every meeting on the page: School Committee and all subcommittees. Skip meetings dated after today (the page lists upcoming ones). Use America/New_York for "today".
- Take every URL from the raw page HTML, whole. Never take URLs from a summarizing fetch (one truncated a Zoom link, see `ops/issues.md`). Follow redirects.
- Recordings can be YouTube or Zoom. Some links are `share.google` redirects that land on YouTube.
- Save the PDFs inside the agenda packet under `agenda-packet/`. Do not save the combined agenda package PDF.
- Write `meta.json` last, after all files for the meeting are saved. A meeting counts as done only when its `meta.json` has `"status": "complete"`.
- Meetings that are not complete (no recording yet, no transcript yet) are retried on each run until 30 days after the meeting date, then frozen as they are.
- Always regenerate `docs/meetings/index.html` and each meeting's `index.html` from the `meta.json` files with `scripts/meetings/build_site.py`. Never edit the generated HTML by hand.
- Commit only if `git status` shows changes, then push to `main`.

## Issues log

Whenever something goes wrong, even if you worked around it, add a dated entry to `ops/issues.md` (newest first; format is in the file). If the same problem is already logged, update that entry with a "last seen" date instead of adding a duplicate. Commit the log with the rest of the run.

## Style

- Plain, direct writing. No em dashes.
- Surgical edits over rewrites.

# Plan 0001: Generate meeting pages

Last updated: 2026-10-04

## Goal

A daily job, runnable in a Claude Code cloud session, that finds new Brookline Public Schools meetings (School Committee and all subcommittees) on https://www.psbma.org/district/school-committee/meeting-materials, saves their materials into this repo, and publishes a static site. Running it daily must leave the site correct whether zero, one, or several meetings happened since the last run.

For each meeting:
- Recording link (YouTube or Zoom)
- Transcript, if one can be downloaded
- Agenda PDF
- The PDFs inside the agenda packet (not the combined package PDF)

Published site (GitHub Pages, deploy from `main`, folder `/docs`):
- `docs/meetings/index.html`: all meetings, newest first, date and title only
- `docs/meetings/<YYYY-MM-DD>-<body-slug>/index.html`: one page per meeting with title, date, recording link, and links to the transcript, agenda, and packet PDFs

## Decisions so far

- **No gists.** Gists are flat and can't be published from a subfolder. Static pages in `docs/` replace them. The per-meeting and list pages the original request called "gist pages" are plain HTML files here.
- **Repo:** `mjlyons/brookline-schools`. Broader than meetings because the repo will also hold analysis. `analysis/` is unpublished and the sync never touches it.
- **State is the filesystem.** Each meeting folder has a `meta.json`, written last. A meeting is done only when its status is `complete`.
- **Pages are generated.** `scripts/meetings/build_site.py` rebuilds every page from the `meta.json` files on every run, so there is no incremental editing to get wrong.
- **Retry window:** incomplete meetings (no recording yet, no transcript yet) are retried daily for 30 days after the meeting, then frozen. The 30 days is my guess; change `RETRY_DAYS` in `sync.py` if you want something else.
- **Upcoming meetings are skipped.** The page lists future meetings (Oct 7 appeared on Oct 4). "Today" is America/New_York.
- **Both Zoom and YouTube recordings.** Some `share.google` links are redirects that land on YouTube.
- **Issues log:** problems go in `ops/issues.md` (unpublished), deduplicated by updating "last seen".
- **Meeting page links:** the user asked for links to "agenda and agenda-package PDFs". I read that as the individual PDFs from the packet, plus an external link to the original combined package on the district site (we don't store the combined file).

## What the source page looks like

From a summarizing fetch, not the raw HTML, so verify before relying on it:
- One long server-rendered list, newest first, no pagination or year filter.
- Each entry has a date, body, and time.
- Agendas link to CivicClerk: `brooklinema.portal.civicclerk.com/event/<id>/files/agenda/<id>`.
- Recordings are a mix of YouTube, Zoom share links, and `share.google` redirects.
- A Zoom share link loads for the user and redirects to a `/rec/play/` page with `canPlayFromShare=true`.

Lesson already learned: the summarizing fetch truncated a Zoom URL, which made a working recording look dead. All URLs must come from raw HTML.

## Done

- Repo created and attached to the cloud session
- `CLAUDE.md` with the rules above
- `/sync-meetings` slash command (`.claude/commands/sync-meetings.md`)
- `scripts/meetings/build_site.py`: working generator for the meeting pages and list
- `scripts/meetings/sync.py`: skeleton with real decision logic (which meetings need work, folder names, retry window); scraping and downloads are TODO
- `docs/` skeleton with `.nojekyll`, landing page, and an empty meetings list
- `ops/issues.md` with the problems found so far

## Still to do

Needs you:
1. Turn on Pages: Settings > Pages > Deploy from a branch > `main` > `/docs`.
2. Add these hosts to the cloud environment's network allowlist: `psbma.org`, `brooklinema.portal.civicclerk.com`, `brooklinema.zoomgov.com`, `share.google`, `youtube.com`, `googlevideo.com`. The sandbox shell is currently blocked from all of them.
3. Allow the cloud task to push directly to `main` (otherwise it lands on a branch and nothing publishes).
4. Skim a few agenda packets for student or personnel details before the first real run. Pages sites are public.

Build, in order:
1. Fetch the raw listing HTML and write `fetch_listing()`. Check whether CivicClerk has a JSON API that is more reliable than scraping.
2. Look at one real agenda packet on CivicClerk: separate attachment files, or one combined PDF? If combined, split by bookmarks with `pypdf`, or decide a fallback if there are none.
3. Resolve recordings: follow `share.google` redirects, classify as YouTube or Zoom.
4. YouTube transcripts with `yt-dlp --skip-download --write-auto-subs --sub-langs en`. YouTube often blocks datacenter IPs, so test this from the cloud environment early. If it fails, record the meeting as incomplete and retry.
5. Zoom transcripts. Unknown whether the play page exposes a transcript or download. Check a real page (the 2026-09-28 DEIJ recording loads for the user). If not, record `no-transcript`.
6. Write `process_meeting()` and its `meta.json` output.
7. Same-day, same-body collisions: two meetings with the same date and body would share a folder name. Detect it and add the CivicClerk event id to the folder name.
8. Run it once by hand, review the output, then create the daily scheduled task.

## Open questions

- Does the Zoom play page offer a transcript or download?
- Are packet attachments separate files or one combined PDF?
- Does YouTube serve transcripts to the cloud environment's IP range?
- Repo size: a year of packets may approach the 1 GB soft limit for Pages. Check a typical packet size after the first run.

## Verification (so far)

`build_site.py` is tested with fake meetings only. Nothing has been run against the live site.

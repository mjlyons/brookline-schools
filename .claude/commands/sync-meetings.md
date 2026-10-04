---
description: Sync new Brookline school meeting materials into docs/ and publish
---

Run the meeting sync for this repo. Follow the rules in CLAUDE.md.

1. `pip install -r requirements.txt` if the dependencies are missing.
2. Run `python scripts/meetings/sync.py`. It scrapes the materials page, finds meetings that are new or incomplete, downloads their files, and rebuilds the site pages.
3. If the script reports a meeting it could not finish, look at why. Handle judgment calls the script can't (odd page layout, a packet with no clear split, a link that changed shape). Fix the script if the cause is a bug.
4. Add or update entries in `ops/issues.md` for anything that went wrong.
5. Run `python scripts/meetings/build_site.py` so the generated pages match the `meta.json` files.
6. If `git status` shows changes, commit and push to `main`. If nothing changed, say so and stop.

Finish with a short summary: how many meetings were new, how many are still incomplete and why, and anything logged to `ops/issues.md`.

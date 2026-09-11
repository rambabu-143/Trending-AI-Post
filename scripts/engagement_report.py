"""Manual helper: print like/comment counts for past posts, keyed to source and hook
formula, so you can see what's actually resonating.

Reads posted_repos.txt for "id|source|hook_formula|post_urn" lines (older entries with
no captured URN are skipped) and queries LinkedIn's Social Actions API for each.

ponytail: LinkedIn's personal-post analytics access varies by app/product grant. If every
row prints "?", your token's scope likely doesn't include social-action reads; the log
itself (source + hook formula per post) is still there to eyeball by hand.

Usage:
    uv run python scripts/engagement_report.py
"""
import os
import sys
import urllib.parse
from pathlib import Path

import requests

POSTED_LOG = Path(__file__).resolve().parent.parent / "posted_repos.txt"

token = os.environ["LINKEDIN_ACCESS_TOKEN"]

if not POSTED_LOG.exists():
    sys.exit("No posted_repos.txt yet.")

print(f"{'id':<45} {'source':<10} {'formula':<14} {'likes':>6} {'comments':>9}")
for line in POSTED_LOG.read_text().splitlines():
    parts = line.split("|")
    if len(parts) < 4 or not parts[3]:
        continue
    item_id, source, formula, post_urn = parts

    resp = requests.get(
        f"https://api.linkedin.com/v2/socialActions/{urllib.parse.quote(post_urn, safe='')}",
        headers={"Authorization": f"Bearer {token}", "X-Restli-Protocol-Version": "2.0.0"},
        timeout=15,
    )
    if resp.status_code == 200:
        data = resp.json()
        likes = data.get("likesSummary", {}).get("totalLikes", "?")
        comments = data.get("commentsSummary", {}).get("totalFirstLevelComments", "?")
    else:
        likes = comments = "?"

    print(f"{item_id:<45} {source:<10} {formula:<14} {likes!s:>6} {comments!s:>9}")

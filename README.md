# trending-repo-bot

Every day, posts one trending item to LinkedIn — a GitHub repo or a Hacker News story,
alternating so one source doesn't crowd out the other. Runs on GitHub Actions — no server needed.

## What it does
1. Pulls today's top GitHub trending repos (`github.com/trending`) and top Hacker News
   stories (HN's official Firebase API), and picks one not already posted — alternating
   source from the last post so both stay in rotation
2. Summarizes it as a post via a local Ollama model: a hook (rotated across a few proven
   openers), a plain-language explanation, one sentence of actual opinion/prediction (not
   just a report), and a closing question — following LinkedIn's 2026 algorithm heuristics
   (no question-opener, closing question, capped hashtags) and voice rules (AI-tell vocab
   scrub, em-dash cap) from [sergebulaev/linkedin-skills](https://github.com/sergebulaev/linkedin-skills)
3. Posts it to LinkedIn via the API, then drops the link as the first comment instead of
   in the body (in-body links get suppressed ~40-60% on LinkedIn)
4. Logs `id|source|hook_formula|post_urn` to `posted_repos.txt` for dedup and for
   `scripts/engagement_report.py` to look up likes/comments later

## Layout
```
src/trending_repo_bot/main.py     # the bot
scripts/get_linkedin_token.py     # one-time OAuth helper
scripts/engagement_report.py      # manual: likes/comments per past post, by source + hook formula
tests/test_main.py
```

## Local setup
Requires [uv](https://docs.astral.sh/uv/).
```bash
uv sync
uv run post-trending          # run the bot
uv run python scripts/get_linkedin_token.py   # get LinkedIn credentials
uv run pytest                 # run tests
```

## One-time setup

### 1. LinkedIn API
You need:
- `LINKEDIN_ACCESS_TOKEN` — token with `w_member_social` scope
- `LINKEDIN_AUTHOR_URN` — your profile URN, looks like `urn:li:person:XXXXXXXXXX`

### 2. Push this repo to GitHub
```bash
gh repo create trending-repo-bot --private --source=. --push
```
(or create it manually on github.com and `git remote add origin <url> && git push -u origin main`)

### 3. Add secrets
Repo → Settings → Secrets and variables → Actions → New repository secret:
`LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_URN`

### 4. Test it
Actions tab → "Daily trending repo post" → Run workflow (manual trigger), check it posts correctly.
After that it runs automatically every day at 9:00 AM IST (edit the cron in
`.github/workflows/daily-post.yml` to change the time).

## Notes
- LinkedIn access tokens from the standard OAuth flow expire (~60 days). If posts stop working, refresh the token and update the secret.
- If GitHub changes their trending page HTML, `get_github_trending()` in `src/trending_repo_bot/main.py` may need a selector tweak.
- `scripts/engagement_report.py` depends on LinkedIn's Social Actions API returning like/comment counts for personal posts, which some app/token grants don't include — if every row prints `?`, that's a scope limit, not a bug.
- `posted_repos.txt` is tracked in git — the workflow commits it back after each run so dedup state survives across the ephemeral GitHub Actions runner. Don't also run the bot from a local cron/launchd job against the same repo; two schedulers with unsynced copies of this file can double-post.

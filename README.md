# trending-repo-bot

Every day, posts today's top 5 GitHub trending repos to LinkedIn.
Runs on GitHub Actions — no server needed.

## What it does
1. Scrapes `github.com/trending?since=daily`
2. Summarizes the repo as a post via a local Ollama model, following LinkedIn's 2026 algorithm
   heuristics (number-first opener, no question opener, closing question, capped hashtags) —
   see [sergebulaev/linkedin-skills](https://github.com/sergebulaev/linkedin-skills) for the
   source rules
3. Posts it to LinkedIn via the API, then drops the repo link as the first comment instead of
   in the body (in-body links get suppressed ~40-60% on LinkedIn)

## Layout
```
src/trending_repo_bot/main.py   # the bot
scripts/get_linkedin_token.py   # one-time OAuth helper
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
- If GitHub changes their trending page HTML, `get_trending()` in `src/trending_repo_bot/main.py` may need a selector tweak.

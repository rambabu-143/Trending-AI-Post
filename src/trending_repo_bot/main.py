"""Fetch today's GitHub trending repos, summarize with a local Ollama model, and post to LinkedIn."""
import os
import re
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

FETCH_N = 25  # buffer to search through for one not already posted
OLLAMA_MODEL = "llama3.2"
POSTED_LOG = Path(__file__).resolve().parents[2] / "posted_repos.txt"  # repo root

# ponytail: fixed word-swap list, not a real style model — extend as new AI tells show up.
AI_VOCAB = {
    "game-changing": "useful",
    "game-changer": "a real fix",
    "leverage": "use",
    "delve into": "look at",
    "delve": "look at",
    "fundamentally": "",
    "in today's fast-paced world": "",
    "streamline": "simplify",
    "unlock": "open up",
    "foster": "build",
    "the result?": "",
    "plot twist:": "",
}

# Hook openers adapted from the Post Writer skill's formula library
# (github.com/sergebulaev/linkedin-skills) — trimmed to the ones that fit a
# one-repo announcement. Picked per repo so daily posts don't all read the same.
HOOK_FORMULAS = {
    "number_stat": (
        "Line 1 is a specific number about the problem this repo solves (hours wasted, "
        "repos that reinvent this, how often it comes up) — a statement, never a question."
    ),
    "contrarian": (
        "Line 1 names the common, harder way developers currently solve this problem, as a "
        "flat statement — no question, no 'here's how'."
    ),
    "curiosity_gap": (
        "Line 1 is a specific, concrete tease about what this repo does that pays off within "
        "the next 2 lines — a real detail, not a vague tease like 'what nobody tells you'."
    ),
    "explain_kids": (
        "Line 1 is a one-sentence real-world scenario (a statement, not a question) that "
        "mirrors the problem this repo solves."
    ),
}


def _pick_hook_formula(name):
    return list(HOOK_FORMULAS)[sum(name.encode()) % len(HOOK_FORMULAS)]


def get_trending(language=""):
    url = f"https://github.com/trending/{language}?since=daily"
    html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15).text
    soup = BeautifulSoup(html, "html.parser")
    repos = []
    for article in soup.select("article.Box-row")[:FETCH_N]:
        name = article.select_one("h2 a")["href"].strip("/")
        desc_tag = article.select_one("p")
        desc = desc_tag.text.strip() if desc_tag else ""
        stars_tag = article.select_one("span.d-inline-block.float-sm-right")
        stars_today = stars_tag.text.strip() if stars_tag else ""
        repos.append({"name": name, "desc": desc, "stars_today": stars_today})
    return repos


def already_posted():
    if not POSTED_LOG.exists():
        return set()
    return set(POSTED_LOG.read_text().splitlines())


def mark_posted(name):
    with POSTED_LOG.open("a") as f:
        f.write(name + "\n")


def pick_unposted(repos):
    posted = already_posted()
    for r in repos:
        if r["name"] not in posted:
            return r
    return None


def summarize(name, desc):
    # Rules below follow LinkedIn's 2026 algorithm heuristics (question openers and
    # in-body links both get penalized — see sergebulaev/linkedin-skills reference repo).
    hook_rule = HOOK_FORMULAS[_pick_hook_formula(name)]
    prompt = (
        f"Repo: {name}\nGitHub description: {desc}\n\n"
        "Write a LinkedIn post about this trending open-source GitHub project, as a short story:\n"
        f"1. {hook_rule}\n"
        "2. Introduce this repo as the solution.\n"
        "3. Explain what it does in 4-6 short sentences, like explaining to a 10-year-old: simple "
        "words, no jargon, use an analogy if it helps.\n"
        "4. Close with one specific question about the reader's own experience with this kind of problem.\n"
        "Style: 900-1300 characters, 1-2 sentence paragraphs with a blank line between them, at most "
        "one em dash total. Avoid 'game-changer', 'leverage', 'delve', 'fundamentally', 'in today's "
        "fast-paced world', 'the result?', 'plot twist:'.\n"
        "Plain text only, no hashtags, no links, no quotes, no markdown."
    )
    resp = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()


def humanize(text):
    """Deterministic backstop for prompt rules the model didn't follow: strip AI-tell
    vocab, cap em dashes at ~1 per 100 words."""
    for bad, good in AI_VOCAB.items():
        pattern = re.escape(bad) if " " in bad else rf"\b{re.escape(bad)}\b"
        text = re.sub(pattern, good, text, flags=re.IGNORECASE)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    cap = max(1, len(text.split()) // 100)
    parts = text.split("—")
    if len(parts) - 1 > cap:
        text = "—".join(parts[: cap + 1]) + ". " + ". ".join(
            p.strip().capitalize() for p in parts[cap + 1:]
        )
    return text.strip()


def format_linkedin(r):
    # No link here — it gets posted as the first comment instead (see comment_with_link):
    # in-body links are suppressed ~40-60%, link-in-first-comment gets ~2.1x reach.
    story = humanize(summarize(r["name"], r["desc"]) or r["desc"])
    return f"{story}\n\n⭐ {r['name']} ({r['stars_today']} today)\n\n#OpenSource #GitHub"


def post_to_linkedin(text):
    """Publish the post and return its URN (for the follow-up link comment)."""
    token = os.environ["LINKEDIN_ACCESS_TOKEN"]
    author = os.environ["LINKEDIN_AUTHOR_URN"]  # e.g. urn:li:person:XXXXXXXX
    resp = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        json={
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.headers.get("x-restli-id") or (resp.json().get("id") if resp.content else None)


def comment_with_link(post_urn, repo_url):
    if not post_urn:
        return
    token = os.environ["LINKEDIN_ACCESS_TOKEN"]
    author = os.environ["LINKEDIN_AUTHOR_URN"]
    encoded_urn = urllib.parse.quote(post_urn, safe="")
    resp = requests.post(
        f"https://api.linkedin.com/v2/socialActions/{encoded_urn}/comments",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        json={"actor": author, "message": {"text": f"Repo: {repo_url}"}},
        timeout=15,
    )
    resp.raise_for_status()


def main():
    repos = get_trending()
    if not repos:
        raise SystemExit("No trending repos found — GitHub markup may have changed.")
    repo = pick_unposted(repos)
    if repo is None:
        raise SystemExit("All of today's trending repos were already posted before — nothing new to post.")
    post_urn = post_to_linkedin(format_linkedin(repo))
    try:
        comment_with_link(post_urn, f"https://github.com/{repo['name']}")
    except requests.HTTPError as e:
        print(f"Posted, but couldn't attach the link comment: {e}")
    mark_posted(repo["name"])
    print(f"Posted {repo['name']} to LinkedIn.")


if __name__ == "__main__":
    main()

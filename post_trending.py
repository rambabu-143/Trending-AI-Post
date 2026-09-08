"""Fetch today's GitHub trending repos, summarize with a local Ollama model, and post to LinkedIn."""
import os
from pathlib import Path

import requests
from bs4 import BeautifulSoup

FETCH_N = 25  # buffer to search through for one not already posted
OLLAMA_MODEL = "llama3.2"
POSTED_LOG = Path(__file__).parent / "posted_repos.txt"


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
    prompt = (
        f"Repo: {name}\nGitHub description: {desc}\n\n"
        "Write a LinkedIn post about this trending open-source GitHub project, as a short story:\n"
        "1. Open with a relatable hook — a question or scenario about a problem developers face "
        "('Ever wondered how...?' / 'Imagine you had to...'), tied to what this repo actually solves.\n"
        "2. Introduce this repo as the solution.\n"
        "3. Explain what it does in 4-6 short sentences, like explaining to a 10-year-old: simple "
        "words, no jargon, use an analogy if it helps.\n"
        "4. End with who would find this useful.\n"
        "Plain text only, no hashtags, no quotes, no markdown."
    )
    resp = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()


def format_linkedin(r):
    story = summarize(r["name"], r["desc"]) or r["desc"]
    return (
        f"{story}\n\n"
        f"⭐ {r['name']} ({r['stars_today']}) — https://github.com/{r['name']}\n\n"
        f"#OpenSource #GitHub #SoftwareEngineering #Trending"
    )


def post_to_linkedin(text):
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


if __name__ == "__main__":
    repos = get_trending()
    if not repos:
        raise SystemExit("No trending repos found — GitHub markup may have changed.")
    repo = pick_unposted(repos)
    if repo is None:
        raise SystemExit("All of today's trending repos were already posted before — nothing new to post.")
    post_to_linkedin(format_linkedin(repo))
    mark_posted(repo["name"])
    print(f"Posted {repo['name']} to LinkedIn.")

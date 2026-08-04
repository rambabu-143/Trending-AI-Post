"""Fetch today's GitHub trending repos and post a roundup to LinkedIn."""
import os
import requests
from bs4 import BeautifulSoup

TOP_N = 5


def get_trending(language=""):
    url = f"https://github.com/trending/{language}?since=daily"
    html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15).text
    soup = BeautifulSoup(html, "html.parser")
    repos = []
    for article in soup.select("article.Box-row")[:TOP_N]:
        name = article.select_one("h2 a")["href"].strip("/")
        desc_tag = article.select_one("p")
        desc = desc_tag.text.strip() if desc_tag else ""
        stars_tag = article.select_one("span.d-inline-block.float-sm-right")
        stars_today = stars_tag.text.strip() if stars_tag else ""
        repos.append({"name": name, "desc": desc, "stars_today": stars_today})
    return repos


def format_linkedin(repos):
    lines = ["🔥 Today's trending open-source repos on GitHub:\n"]
    for r in repos:
        lines.append(f"⭐ {r['name']} ({r['stars_today']})\n   {r['desc']}\n   https://github.com/{r['name']}")
    lines.append("\n#OpenSource #GitHub #SoftwareEngineering #Trending")
    return "\n".join(lines)


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
    post_to_linkedin(format_linkedin(repos))
    print(f"Posted {len(repos)} trending repos to LinkedIn.")

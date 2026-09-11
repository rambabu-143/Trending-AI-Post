"""Fetch today's GitHub trending repos, summarize with a local Ollama model, and post to LinkedIn."""
import os
import re
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

GITHUB_FETCH_N = 25  # buffer to search through for one not already posted
HN_FETCH_N = 15
OLLAMA_MODEL = "llama3.2"
POSTED_LOG = Path(__file__).resolve().parents[2] / "posted_repos.txt"  # repo root

# ponytail: fixed word-swap list, not a real style model. Extend as new AI tells show up.
AI_VOCAB = {
    "game-changing": "useful",
    "game-changer": "a real fix",
    "leverage": "use",
    "delve into": "look at",
    "delve": "look at",
    "fundamentally": "",
    "in today's fast-paced world": "",
    "in the age of ai": "",
    "at the end of the day": "",
    "streamline": "simplify",
    "unlock": "open up",
    "foster": "build",
    "deep dive": "look",
    "move the needle": "change the numbers",
    "paradigm shift": "real shift",
    "pivotal moment": "the moment",
    "testament to": "shows",
    "the result?": "",
    "plot twist:": "",
}

# Reveal-bridge / templated-rhythm patterns models default to (from the linkedin-skills
# humanizer reference), regex-anchored so they catch more than an exact literal match.
REVEAL_BRIDGE_PATTERNS = [
    r"(?im)^here'?s (what|how|why|the thing)\b[^:.\n]{0,40}[:.]\s*",
    r"(?im)^(plot twist|spoiler|the twist)[:?]\s*",
    r"(?im)^stop \w[^,.]{0,40}[,.]\s*start\s+",
]
NEG_PARALLEL_PATTERN = r"(?i)\bit'?s not \w[^,.]{0,40},\s*it'?s\s+"

# Hook openers adapted from the Post Writer skill's formula library
# (github.com/sergebulaev/linkedin-skills), trimmed to the ones that fit a
# one-repo announcement. Picked per repo so daily posts don't all read the same.
HOOK_FORMULAS = {
    "number_stat": (
        "Line 1 is a specific number about the problem this repo solves (hours wasted, "
        "repos that reinvent this, how often it comes up), a statement, never a question."
    ),
    "contrarian": (
        "Line 1 names the common, harder way developers currently solve this problem, as a "
        "flat statement, no question, no 'here's how'."
    ),
    "curiosity_gap": (
        "Line 1 is a specific, concrete tease about what this repo does that pays off within "
        "the next 2 lines, a real detail, not a vague tease like 'what nobody tells you'."
    ),
    "explain_kids": (
        "Line 1 is a one-sentence real-world scenario (a statement, not a question) that "
        "mirrors the problem this repo solves."
    ),
}


def _pick_hook_formula(name):
    return list(HOOK_FORMULAS)[sum(name.encode()) % len(HOOK_FORMULAS)]


def get_github_trending(language=""):
    """Trending GitHub repos as source-agnostic items (id/title/desc/url/metric/source)."""
    url = f"https://github.com/trending/{language}?since=daily"
    html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15).text
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for article in soup.select("article.Box-row")[:GITHUB_FETCH_N]:
        name = article.select_one("h2 a")["href"].strip("/")
        desc_tag = article.select_one("p")
        desc = desc_tag.text.strip() if desc_tag else ""
        stars_tag = article.select_one("span.d-inline-block.float-sm-right")
        stars_today = stars_tag.text.strip() if stars_tag else ""
        items.append({
            "id": name,  # bare "owner/repo", matches the pre-existing posted_repos.txt format
            "title": name,
            "desc": desc,
            "url": f"https://github.com/{name}",
            "metric": stars_today,
            "source": "github",
        })
    return items


def get_hn_trending():
    """Top Hacker News stories with an external link, via HN's official Firebase API."""
    ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=15).json()
    items = []
    for story_id in ids[:HN_FETCH_N]:
        story = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=15).json()
        if not story or story.get("type") != "story" or not story.get("url"):
            continue  # skip Ask/Show HN text posts, jobs, and dead/deleted items
        items.append({
            "id": f"hn:{story_id}",
            "title": story.get("title", ""),
            "desc": "",
            "url": story["url"],
            "metric": f"{story.get('score', 0)} points, {story.get('descendants', 0)} comments",
            "source": "hackernews",
        })
    return items


def get_trending():
    return get_github_trending() + get_hn_trending()


def already_posted():
    if not POSTED_LOG.exists():
        return set()
    # older entries are a bare id; newer ones are "id|source|hook_formula|post_urn"; id is always field 0
    return {line.split("|", 1)[0] for line in POSTED_LOG.read_text().splitlines() if line}


def _last_posted_source():
    if not POSTED_LOG.exists():
        return None
    lines = [l for l in POSTED_LOG.read_text().splitlines() if l]
    if not lines:
        return None
    fields = lines[-1].split("|")
    return fields[1] if len(fields) > 1 else "github"  # pre-source entries were all GitHub


def mark_posted(item, post_urn):
    with POSTED_LOG.open("a") as f:
        f.write(f"{item['id']}|{item['source']}|{_pick_hook_formula(item['id'])}|{post_urn or ''}\n")


def pick_unposted(items):
    posted = already_posted()
    candidates = [i for i in items if i["id"] not in posted]
    if not candidates:
        return None
    # alternate sources day to day so GitHub's big daily-fresh list doesn't crowd out HN
    last_source = _last_posted_source()
    for i in candidates:
        if i["source"] != last_source:
            return i
    return candidates[0]


def summarize(item):
    # Rules below follow LinkedIn's 2026 algorithm heuristics (question openers and
    # in-body links both get penalized, see sergebulaev/linkedin-skills reference repo).
    hook_rule = HOOK_FORMULAS[_pick_hook_formula(item["id"])]
    kind = "trending open-source GitHub project" if item["source"] == "github" else "story trending on Hacker News"
    prompt = (
        f"Title: {item['title']}\nDescription: {item['desc']}\n\n"
        f"Write a LinkedIn post about this {kind}, as a short story:\n"
        f"1. {hook_rule}\n"
        "2. Introduce it as the solution / the thing worth knowing about.\n"
        "3. Explain what it is in 3-5 short sentences, like explaining to a 10-year-old: simple "
        "words, no jargon, use an analogy if it helps.\n"
        "4. Add one sentence of your own specific opinion or prediction: why this actually "
        "matters or where it's headed. Not generic praise: a real stance someone could disagree with.\n"
        "5. Close with one specific question about the reader's own experience with this kind of problem.\n"
        "Style: 900-1300 characters, 1-2 sentence paragraphs with a blank line between them. "
        "No dashes anywhere, not em dashes and not a hyphen with spaces around it either "
        "(' - '). Use a comma or period instead. Avoid 'game-changer', 'leverage', "
        "'delve', 'fundamentally', 'in today's fast-paced world', 'the result?', 'plot twist:'.\n"
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
    vocab and reveal-bridge phrasing, straighten quotes, and strip every dash-like
    separator. Covers the em dash, en dash, double-hyphen, and a spaced-out single
    hyphen (llama3.2's own substitute when asked not to use dashes). No cap, no exceptions."""
    for bad, good in AI_VOCAB.items():
        pattern = re.escape(bad) if " " in bad else rf"\b{re.escape(bad)}\b"
        text = re.sub(pattern, good, text, flags=re.IGNORECASE)

    for pattern in REVEAL_BRIDGE_PATTERNS:
        text = re.sub(pattern, "", text)
    text = re.sub(NEG_PARALLEL_PATTERN, "it's ", text)

    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")

    def _dash_repl(m):
        # if the text right before the dash already ends a sentence, just close the
        # gap (no extra period); otherwise join with a comma
        return " " if m.string[:m.start()].rstrip()[-1:] in ".!?" else ", "

    text = re.sub(r"\s+[-–—]{1,2}\s+", _dash_repl, text)  # spaced dash-like separator, any flavor
    text = re.sub(r"[—–]", ", ", text)  # any dash left with no surrounding space
    text = re.sub(r"(?<=[.!?]\s)([a-z])", lambda m: m.group(1).upper(), text)  # re-capitalize after a new "."
    text = re.sub(r"[,.]\s*,", ",", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_linkedin(item):
    # No link, no stats line, just the story and hashtags. The link goes out as the
    # first comment instead (see comment_with_link): in-body links are suppressed
    # ~40-60%, link-in-first-comment gets ~2.1x reach.
    story = humanize(summarize(item) or item["desc"] or item["title"])
    tag = "#OpenSource #GitHub" if item["source"] == "github" else "#HackerNews #Tech"
    return f"{story}\n\n{tag}"


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
    items = get_trending()
    if not items:
        raise SystemExit("No trending items found. GitHub/HN markup or API may have changed.")
    item = pick_unposted(items)
    if item is None:
        raise SystemExit("Everything currently trending was already posted before, nothing new to post.")
    post_urn = post_to_linkedin(format_linkedin(item))
    try:
        comment_with_link(post_urn, item["url"])
    except requests.HTTPError as e:
        print(f"Posted, but couldn't attach the link comment: {e}")
    mark_posted(item, post_urn)
    print(f"Posted [{item['source']}] {item['title']} to LinkedIn.")


if __name__ == "__main__":
    main()

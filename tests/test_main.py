import trending_repo_bot.main as bot
from trending_repo_bot.main import HOOK_FORMULAS, _pick_hook_formula, humanize, pick_unposted

_item = {"id": "foo/bar", "title": "foo/bar", "desc": "A cool tool", "metric": "1,234 today", "source": "github"}


def test_pick_unposted():
    assert pick_unposted([_item])["id"] == "foo/bar"


def test_pick_unposted_alternates_source(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, "POSTED_LOG", tmp_path / "posted.txt")
    bot.POSTED_LOG.write_text("owner/repo|github|number_stat|urn:li:ugcPost:1\n")
    items = [
        {"id": "owner/repo2", "source": "github"},
        {"id": "hn:1", "source": "hackernews"},
    ]
    assert pick_unposted(items)["id"] == "hn:1"


def test_humanize_scrubs_vocab_and_caps_em_dashes():
    text = "This is a game-changing leverage play — and here — and here — and here."
    out = humanize(text)
    assert "game-changing" not in out.lower()
    assert "leverage" not in out.lower()
    assert out.count("—") <= 1


def test_pick_hook_formula_is_deterministic_and_valid():
    assert _pick_hook_formula("foo/bar") in HOOK_FORMULAS
    assert _pick_hook_formula("foo/bar") == _pick_hook_formula("foo/bar")

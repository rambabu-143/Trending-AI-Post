from trending_repo_bot.main import HOOK_FORMULAS, _pick_hook_formula, humanize, pick_unposted

_repo = {"name": "foo/bar", "desc": "A cool tool", "stars_today": "1,234 stars today"}


def test_pick_unposted():
    assert pick_unposted([_repo])["name"] == "foo/bar"


def test_humanize_scrubs_vocab_and_caps_em_dashes():
    text = "This is a game-changing leverage play — and here — and here — and here."
    out = humanize(text)
    assert "game-changing" not in out.lower()
    assert "leverage" not in out.lower()
    assert out.count("—") <= 1


def test_pick_hook_formula_is_deterministic_and_valid():
    assert _pick_hook_formula("foo/bar") in HOOK_FORMULAS
    assert _pick_hook_formula("foo/bar") == _pick_hook_formula("foo/bar")

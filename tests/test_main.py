from trending_repo_bot.main import pick_unposted

_repo = {"name": "foo/bar", "desc": "A cool tool", "stars_today": "1,234 stars today"}


def test_pick_unposted():
    assert pick_unposted([_repo])["name"] == "foo/bar"

from post_trending import format_linkedin, pick_unposted

_repo = {"name": "foo/bar", "desc": "A cool tool", "stars_today": "1,234 stars today"}

result = format_linkedin(_repo)
assert "foo/bar" in result
assert "https://github.com/foo/bar" in result

assert pick_unposted([_repo])["name"] == "foo/bar"
print("ok")

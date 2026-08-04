from post_trending import format_linkedin

_repos = [{"name": "foo/bar", "desc": "A cool tool", "stars_today": "1,234 stars today"}]

assert "foo/bar" in format_linkedin(_repos)
assert "A cool tool" in format_linkedin(_repos)
print("ok")

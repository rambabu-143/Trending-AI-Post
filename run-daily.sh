#!/bin/bash
# launchd fires this hourly. Posts once per weekday at a date-hashed random hour (9-16) plus a random
# minute offset; if the Mac was asleep then, it catches up later the same day (until 8pm).
cd "$(dirname "$0")"
d=$(date +%Y%m%d); h=$(date +%-H)
[ "$(date +%u)" -le 5 ] || exit 0
target=$(( 9 + $(echo "$d" | cksum | cut -d' ' -f1) % 8 ))
[ "$h" -ge "$target" ] && [ "$h" -lt 20 ] || exit 0
[ "$(cat .last_post_day 2>/dev/null)" = "$d" ] && exit 0
echo "$d" > .last_post_day  # mark first so an overlapping hourly run can't double-post
sleep $((RANDOM % 3000))
set -a; . ~/.trending-bot.env; set +a
~/.local/bin/uv run --project . post-trending || { rm -f .last_post_day; exit 1; }

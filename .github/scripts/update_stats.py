"""Refresh the contribution-stats card shown in README.md.

This script queries the GitHub GraphQL API for the public contribution
data of a single user, computes the same figures the old streak-stats
card used to show (total contributions, current streak, longest streak),
draws a self-contained SVG card that looks like that card, and rewrites
the block between the <!--STATS:START--> / <!--STATS:END--> markers in
README.md to embed it.

It only relies on the GITHUB_TOKEN that GitHub Actions provides
automatically, so no extra secret needs to be created, and the resulting
image is a plain file in this repo (contribution-stats.svg) rather than
a request to a third-party service, so there is no shared cache to go
stale.
"""

import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone

LOGIN = "kanth071"
README_PATH = "README.md"
SVG_PATH = "contribution-stats.svg"

BG = "#0D1117"
BORDER = "#141B2D"
DIVIDER = "#30363D"
NUMBER = "#C9D1D9"
LABEL = "#8B949E"
RING = "#D4AF37"


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt_short(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %-d")


def fetch_stats(token):
    now = datetime.now(timezone.utc)
    year_start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
    last_year_start = now - timedelta(days=365)

    query = """
    query($login: String!, $thisYearFrom: DateTime!, $lastYearFrom: DateTime!, $to: DateTime!) {
      user(login: $login) {
        followers { totalCount }
        thisYear: contributionsCollection(from: $thisYearFrom, to: $to) {
          contributionCalendar { totalContributions }
        }
        lastYear: contributionsCollection(from: $lastYearFrom, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays { date contributionCount }
            }
          }
        }
      }
    }
    """

    variables = {
        "login": LOGIN,
        "thisYearFrom": iso(year_start),
        "lastYearFrom": iso(last_year_start),
        "to": iso(now),
    }

    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": LOGIN,
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)

    if "errors" in result:
        raise SystemExit(f"GraphQL errors: {result['errors']}")

    user = result["data"]["user"]
    calendar = user["lastYear"]["contributionCalendar"]

    days = []
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append((day["date"], day["contributionCount"]))
    days.sort(key=lambda item: item[0])

    today_str = now.strftime("%Y-%m-%d")

    # Current streak: consecutive contributing days ending today. If today
    # has no contribution yet, don't zero the streak out for that reason
    # alone -- anchor on yesterday instead, same as the badges people are
    # used to.
    start_idx = len(days) - 1
    if days and days[start_idx][0] == today_str and days[start_idx][1] == 0:
        start_idx -= 1

    current_streak = 0
    current_start = current_end = None
    i = start_idx
    while i >= 0 and days[i][1] > 0:
        if current_streak == 0:
            current_end = days[i][0]
        current_start = days[i][0]
        current_streak += 1
        i -= 1

    # Longest streak within the last-365-day window.
    longest_streak = 0
    longest_start = longest_end = None
    run = 0
    run_start = None
    for date, count in days:
        if count > 0:
            if run == 0:
                run_start = date
            run += 1
            if run > longest_streak:
                longest_streak = run
                longest_start = run_start
                longest_end = date
        else:
            run = 0

    return {
        "year": now.year,
        "this_year_total": user["thisYear"]["contributionCalendar"]["totalContributions"],
        "last_year_total": calendar["totalContributions"],
        "followers": user["followers"]["totalCount"],
        "updated": now.strftime("%Y-%m-%d %H:%M UTC"),
        "current_streak": current_streak,
        "current_range": (
            f"{fmt_short(current_start)} - {fmt_short(current_end)}"
            if current_streak
            else "No streak yet"
        ),
        "longest_streak": longest_streak,
        "longest_range": (
            f"{fmt_short(longest_start)} - {fmt_short(longest_end)}"
            if longest_streak
            else "No streak yet"
        ),
    }


def build_svg(stats):
    width, height = 495, 195
    col1_x, col2_x, col3_x = 90, 247, 405

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, Helvetica, Arial, sans-serif">
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="16" fill="{BG}" stroke="{BORDER}"/>

  <line x1="165" y1="28" x2="165" y2="167" stroke="{DIVIDER}" stroke-width="1"/>
  <line x1="330" y1="28" x2="330" y2="167" stroke="{DIVIDER}" stroke-width="1"/>

  <text x="{col1_x}" y="66" font-size="34" font-weight="700" fill="{NUMBER}" text-anchor="middle">{stats["this_year_total"]}</text>
  <text x="{col1_x}" y="108" font-size="13" fill="{LABEL}" text-anchor="middle">Total Contributions</text>
  <text x="{col1_x}" y="127" font-size="11" fill="{LABEL}" text-anchor="middle">{stats["year"]}</text>

  <circle cx="{col2_x}" cy="72" r="38" fill="none" stroke="{RING}" stroke-width="4"/>
  <text x="{col2_x}" y="63" font-size="16" text-anchor="middle">&#128293;</text>
  <text x="{col2_x}" y="88" font-size="24" font-weight="700" fill="{NUMBER}" text-anchor="middle">{stats["current_streak"]}</text>
  <text x="{col2_x}" y="136" font-size="13" fill="{LABEL}" text-anchor="middle">Current Streak</text>
  <text x="{col2_x}" y="155" font-size="11" fill="{LABEL}" text-anchor="middle">{stats["current_range"]}</text>

  <text x="{col3_x}" y="66" font-size="34" font-weight="700" fill="{NUMBER}" text-anchor="middle">{stats["longest_streak"]}</text>
  <text x="{col3_x}" y="108" font-size="13" fill="{LABEL}" text-anchor="middle">Longest Streak</text>
  <text x="{col3_x}" y="127" font-size="11" fill="{LABEL}" text-anchor="middle">{stats["longest_range"]}</text>
</svg>
"""


def update_readme(image_tag):
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    block = (
        "<!--STATS:START-->\n"
        f"{image_tag}\n"
        "<!--STATS:END-->"
    )

    new_content, count = re.subn(
        r"<!--STATS:START-->.*?<!--STATS:END-->",
        lambda _match: block,
        content,
        flags=re.DOTALL,
    )

    if count == 0:
        raise SystemExit("STATS markers not found in README.md")

    if new_content != content:
        with open(README_PATH, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("README.md updated.")
    else:
        print("README.md already up to date.")


def main():
    token = os.environ["GH_TOKEN"]
    stats = fetch_stats(token)

    svg = build_svg(stats)
    with open(SVG_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {SVG_PATH} (updated {stats['updated']}).")

    image_tag = f'<img src="{SVG_PATH}" alt="contribution stats"/>'
    update_readme(image_tag)


if __name__ == "__main__":
    main()

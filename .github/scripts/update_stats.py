"""Refresh the exact GitHub contribution numbers shown in README.md.

This script queries the GitHub GraphQL API for the public contribution
totals of a single user and rewrites the block between the
<!--STATS:START--> / <!--STATS:END--> markers in README.md with the
current, exact figures. It only relies on the GITHUB_TOKEN that GitHub
Actions provides automatically, so no extra secret needs to be created.
"""

import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone

LOGIN = "kanth071"
README_PATH = "README.md"


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


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
          contributionCalendar { totalContributions }
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
    return {
        "year": now.year,
        "this_year_total": user["thisYear"]["contributionCalendar"]["totalContributions"],
        "last_year_total": user["lastYear"]["contributionCalendar"]["totalContributions"],
        "followers": user["followers"]["totalCount"],
        "updated": now.strftime("%Y-%m-%d %H:%M UTC"),
    }


def build_block(stats):
    total_badge = (
        f'<img src="https://img.shields.io/badge/TOTAL_CONTRIBUTIONS_{stats["year"]}-'
        f'{stats["this_year_total"]}-4F8EF7?style=for-the-badge&labelColor=141B2D" '
        f'alt="total contributions {stats["year"]}"/>'
    )
    last_year_badge = (
        f'<img src="https://img.shields.io/badge/LAST_365_DAYS-'
        f'{stats["last_year_total"]}-2EC4B6?style=for-the-badge&labelColor=141B2D" '
        f'alt="contributions last 365 days"/>'
    )

    return (
        "<!--STATS:START-->\n"
        f"{total_badge}\n"
        f"{last_year_badge}\n\n"
        f'<sub>Last updated: {stats["updated"]} · auto-refreshed via GitHub Actions</sub>\n'
        "<!--STATS:END-->"
    )


def update_readme(block):
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

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
        print("README.md updated with fresh contribution stats.")
    else:
        print("No changes needed; stats already up to date.")


def main():
    token = os.environ["GH_TOKEN"]
    stats = fetch_stats(token)
    block = build_block(stats)
    update_readme(block)


if __name__ == "__main__":
    main()

import json
import os
import urllib.request
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path

USERNAME = os.environ.get("GITHUB_USERNAME", "AryanMauryahere")
TOKEN = os.environ["GITHUB_TOKEN"]
OUTPUT = Path("header.svg/github-stats.svg")


def github_request(url, payload=None):
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "github-stats-dashboard",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def get_contribution_data():
    query = """
    query($login: String!) {
      user(login: $login) {
        repositories(ownerAffiliations: OWNER, first: 100, isFork: false) {
          totalCount
          nodes {
            name
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name } }
            }
          }
        }
        contributionsCollection {
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
    result = github_request(
        "https://api.github.com/graphql",
        {"query": query, "variables": {"login": USERNAME}},
    )
    if result.get("errors"):
        raise RuntimeError(result["errors"])
    return result["data"]["user"]


def streaks(days):
    counts = [day["contributionCount"] for day in days]
    current = 0
    for count in reversed(counts):
        if count == 0:
            break
        current += 1

    longest = run = 0
    for count in counts:
        run = run + 1 if count else 0
        longest = max(longest, run)
    return current, longest


def language_totals(repositories):
    totals = Counter()
    for repository in repositories:
        for edge in repository["languages"]["edges"]:
            totals[edge["node"]["name"]] += edge["size"]
    return totals.most_common(5)


def render_bars(weekday_totals):
    maximum = max(weekday_totals) or 1
    bars = []
    for index, count in enumerate(weekday_totals):
        height = round(150 * count / maximum)
        x = 82 + index * 160
        y = 560 - height
        bars.append(
            f'<rect class="bar" x="{x}" y="{y}" width="76" height="{height}" '
            f'rx="12" data-count="{count}"><title>{count} contributions</title></rect>'
        )
    return "".join(bars)


def render_languages(languages):
    total = sum(size for _, size in languages) or 1
    rows = []
    colors = ["#5eead4", "#818cf8", "#c084fc", "#f59e0b", "#22d3ee"]
    for index, (name, size) in enumerate(languages):
        percentage = round(size * 100 / total)
        y = 690 + index * 14
        rows.append(
            f'<circle cx="70" cy="{y - 4}" r="4" fill="{colors[index]}"/>'
            f'<text x="82" y="{y}" fill="#c9d2f5" font-size="12">{escape(name)}</text>'
            f'<text x="500" y="{y}" text-anchor="end" fill="#8b94b3" font-size="12">{percentage}%</text>'
        )
    return "".join(rows)


def main():
    user = get_contribution_data()
    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = [
        day
        for week in calendar["weeks"]
        for day in week["contributionDays"]
    ]
    current, longest = streaks(days)
    weekday_totals = [0] * 7
    for day in days:
        weekday_totals[datetime.fromisoformat(day["date"]).weekday()] += day["contributionCount"]
    weekday_totals = weekday_totals[-1:] + weekday_totals[:-1]
    languages = language_totals(user["repositories"]["nodes"])

    svg = OUTPUT.read_text(encoding="utf-8")
    svg = svg.replace(">0</text>", f">{calendar['totalContributions']}</text>", 1)
    svg = svg.replace('id="current-streak" x="600" y="211" text-anchor="middle" fill="#e8ecf8" font-size="38" font-weight="800">0',
                      f'id="current-streak" x="600" y="211" text-anchor="middle" fill="#e8ecf8" font-size="38" font-weight="800">{current}')
    svg = svg.replace('id="longest-streak" x="685" y="250" class="value">0',
                      f'id="longest-streak" x="685" y="250" class="value">{longest}')
    svg = svg.replace('id="repo-count" x="888" y="222" class="value">0',
                      f'id="repo-count" x="888" y="222" class="value">{user["repositories"]["totalCount"]}')
    svg = svg.replace('<g id="weekday-bars" fill="url(#barFill)"></g>',
                      f'<g id="weekday-bars" fill="url(#barFill)">{render_bars(weekday_totals)}</g>')
    svg = svg.replace('<g id="repo-languages"></g>',
                      f'<g id="repo-languages">{render_languages(languages)}</g>')
    svg = svg.replace("Loading GitHub data...",
                      f"{calendar['totalContributions']} contributions in the last year")
    circumference = 2 * 3.14159 * 65
    progress = min(current / max(longest, 1), 1) * circumference
    svg = svg.replace('stroke-dasharray="0 408.4"',
                      f'stroke-dasharray="{progress:.1f} {circumference:.1f}"')
    OUTPUT.write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    main()

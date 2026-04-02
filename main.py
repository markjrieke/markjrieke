import os
import requests
from pathlib import Path

GITHUB_TOKEN = os.environ["GH_TOKEN"]
GITHUB_USERNAME = os.environ["GITHUB_USERNAME"]

OUTPUT_PATH = Path("assets/activity-sparkline.svg")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

def fetch_contributions():
    response = requests.post(
        "https://api.github.com/graphql",
        json={"query": QUERY, "variables": {"login": GITHUB_USERNAME}},
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    if "errors" in data:
        raise RuntimeError(data["errors"])

    weeks = (
        data["data"]["user"]["contributionsCollection"]
        ["contributionCalendar"]["weeks"]
    )

    return [
        {
            "days": week["contributionDays"],
            "count": sum(day["contributionCount"] for day in week["contributionDays"]),
        }
        for week in weeks
    ]

def last_n_weeks(weeks, n=26):
    return weeks[-n:]

def scale_points(counts, width, height, padding_top, padding_bottom, padding_x):
    n = len(counts)
    if n == 0:
        return []

    max_count = max(counts)
    max_count = max(max_count, 1)

    usable_w = width - 2 * padding_x
    usable_h = height - padding_top - padding_bottom

    points = []
    for i, c in enumerate(counts):
        x = padding_x + (usable_w * i / (n - 1 if n > 1 else 1))
        normalized = c / max_count
        y = padding_top + usable_h * (1 - normalized)
        points.append((x, y))
    return points

def smooth_path(points):
    if len(points) < 2:
        return ""

    d = f"M {points[0][0]:.2f},{points[0][1]:.2f}"
    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]
        cx = (x0 + x1) / 2
        d += f" Q {cx:.2f},{y0:.2f} {x1:.2f},{y1:.2f}"
    return d

def area_path(points, base_y):
    if len(points) < 2:
        return ""

    d = f"M {points[0][0]:.2f},{base_y:.2f} "
    d += f"L {points[0][0]:.2f},{points[0][1]:.2f} "

    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]
        cx = (x0 + x1) / 2
        d += f"Q {cx:.2f},{y0:.2f} {x1:.2f},{y1:.2f} "

    d += f"L {points[-1][0]:.2f},{base_y:.2f} Z"
    return d

def build_svg(weeks):
    width = 340
    height = 56
    padding_x = 6
    padding_top = 6
    padding_bottom = 16

    counts = [w["count"] for w in weeks]
    points = scale_points(counts, width, height, padding_top, padding_bottom, padding_x)
    line = smooth_path(points)
    base_y = height - padding_bottom
    fill = area_path(points, base_y)

    svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GitHub activity sparkline">
  <path d="{fill}" fill="#2da44e" fill-opacity="0.12"/>
  <path d="{line}" stroke="#2da44e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>'''
    return svg

def main():
    weeks = fetch_contributions()
    weeks = last_n_weeks(weeks, 26)
    svg = build_svg(weeks)
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
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

    days = []
    for week in weeks:
        for day in week["contributionDays"]:
            days.append({
                "date": day["date"],
                "count": day["contributionCount"]
            })

    return days

def last_n_days(days, n=90):
    return days[-n:]

def scale_points(counts, width, height, padding):
    n = len(counts)
    if n == 0:
        return []

    max_count = max(counts)
    max_count = max(max_count, 1)

    usable_w = width - 2 * padding
    usable_h = height - 2 * padding

    points = []
    for i, c in enumerate(counts):
        x = padding + (usable_w * i / (n - 1 if n > 1 else 1))
        normalized = c / max_count
        y = padding + usable_h * (1 - normalized)
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

def area_path(points, width, height, padding):
    if len(points) < 2:
        return ""

    base_y = height - padding
    d = f"M {points[0][0]:.2f},{base_y:.2f} "
    d += f"L {points[0][0]:.2f},{points[0][1]:.2f} "

    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]
        cx = (x0 + x1) / 2
        d += f"Q {cx:.2f},{y0:.2f} {x1:.2f},{y1:.2f} "

    d += f"L {points[-1][0]:.2f},{base_y:.2f} Z"
    return d

def build_svg(days):
    width = 360
    height = 72
    padding = 8

    counts = [d["count"] for d in days]
    points = scale_points(counts, width, height, padding)

    line = smooth_path(points)
    fill = area_path(points, width, height, padding)

    circles = "\n".join(
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.8" fill="#2da44e" />'
        for x, y in points
    )

    total = sum(counts)
    max_day = max(counts) if counts else 0

    svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GitHub activity sparkline">
  <rect x="0" y="0" width="{width}" height="{height}" rx="12" fill="#0d1117"/>
  <path d="{fill}" fill="#2da44e" fill-opacity="0.14"/>
  <path d="{line}" stroke="#2da44e" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  {circles}
  <text x="{padding}" y="{height - 10}" fill="#8b949e" font-family="system-ui, -apple-system, Segoe UI, sans-serif" font-size="9">
    Last {len(days)} days • {total} contributions • max {max_day}/day
  </text>
</svg>'''
    return svg

def main():
    days = fetch_contributions()
    days = last_n_days(days, 90)
    svg = build_svg(days)
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
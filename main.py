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

def green_for_intensity(value, max_value):
    if max_value <= 0:
        return "#238636"

    ratio = value / max_value

    if ratio <= 0.12:
        return "#1f6f3d"
    elif ratio <= 0.32:
        return "#238636"
    elif ratio <= 0.58:
        return "#2ea043"
    elif ratio <= 0.82:
        return "#3fb950"
    else:
        return "#56d364"

def build_svg(weeks):
    # intentionally compact + repo-pulse-ish
    width = 240
    height = 32
    padding_x = 3
    padding_top = 3
    padding_bottom = 4

    counts = [w["count"] for w in weeks]
    points = scale_points(counts, width, height, padding_top, padding_bottom, padding_x)

    base_y = height - padding_bottom
    fill = area_path(points, base_y)

    max_week = max(counts) if counts else 0

    segment_paths = []
    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]
        cx = (x0 + x1) / 2

        intensity = max(counts[i - 1], counts[i])
        color = green_for_intensity(intensity, max_week)

        segment_paths.append(
            f'<path d="M {x0:.2f},{y0:.2f} Q {cx:.2f},{y0:.2f} {x1:.2f},{y1:.2f}" '
            f'stroke="{color}" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
        )

    segment_svg = "\n  ".join(segment_paths)

    svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GitHub activity sparkline">
  <line x1="{padding_x}" y1="{base_y}" x2="{width - padding_x}" y2="{base_y}" stroke="#30363d" stroke-width="0.8"/>
  <path d="{fill}" fill="#2ea043" fill-opacity="0.06"/>
  {segment_svg}
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
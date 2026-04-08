import os
import json
import argparse
import requests
from pathlib import Path

GITHUB_TOKEN = os.environ["GH_TOKEN"]
GITHUB_USERNAMES = [
    os.environ["GITHUB_USERNAME"],
    "markjrieke-fortisgames"
]

OUTPUT_PATH = Path("assets/activity-sparkline.svg")
CACHE_PATH = Path("assets/activity-data.json")

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

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

def fetch_contributions(username):
    response = requests.post(
        "https://api.github.com/graphql",
        json={"query": QUERY, "variables": {"login": username}},
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

def merge_contributions(all_weeks_list):
    combined = {}
    for weeks in all_weeks_list:
        for week in weeks:
            week_key = week["days"][0]["date"]
            if week_key in combined:
                combined[week_key]["count"] += week["count"]
            else:
                combined[week_key] = {
                    "days": week["days"],
                    "count": week["count"]
                }

    return [combined[k] for k in sorted(combined)]

def last_n_weeks(weeks, n=26):
    return weeks[-n:]

def save_weeks(weeks, path=CACHE_PATH):
    path.write_text(json.dumps(weeks, indent=2), encoding="utf-8")

def load_weeks(path=CACHE_PATH):
    if not path.exists():
        raise FileNotFoundError(
            f"No cached activity data found at {path}. Run with --refresh first."
        )
    return json.loads(path.read_text(encoding="utf-8"))

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

    for x, y in points[1:]:
        d += f"L {x:.2f},{y:.2f} "

    d += f"L {points[-1][0]:.2f},{base_y:.2f} Z"
    return d

def line_path(points):
    if len(points) < 2:
        return ""

    d = f"M {points[0][0]:.2f},{points[0][1]:.2f} "
    for x, y in points[1:]:
        d += f"L {x:.2f},{y:.2f} "
    return d.strip()

def green_for_intensity(value, max_value):
    if max_value <= 0:
        return "#274029"
    ratio = value / max_value
    dark_rgb = (44, 72, 45)     # darker green for more contrast
    bright_rgb = (102, 149, 97) # GitHub-ish bright green
    r = int(dark_rgb[0] + ratio * (bright_rgb[0] - dark_rgb[0]))
    g = int(dark_rgb[1] + ratio * (bright_rgb[1] - dark_rgb[1]))
    b = int(dark_rgb[2] + ratio * (bright_rgb[2] - dark_rgb[2]))
    return f"#{r:02x}{g:02x}{b:02x}"

def gradient_stops(points, counts, width, padding_x, max_value):
    if not points or not counts:
        return ""

    usable_w = width - 2 * padding_x
    if usable_w <= 0:
        usable_w = 1

    stops = []
    for (x, _), count in zip(points, counts):
        offset = ((x - padding_x) / usable_w) * 100
        color = green_for_intensity(count, max_value)
        stops.append(
            f'<stop offset="{offset:.2f}%" stop-color="{color}"/>'
        )

    return "\n      ".join(stops)

def build_svg(weeks):
    width = 180
    height = 30
    padding_x = 3
    padding_top = 0
    padding_bottom = 0

    counts = [w["count"] for w in weeks]
    points = scale_points(counts, width, height, padding_top, padding_bottom, padding_x)

    base_y = height - padding_bottom
    fill = area_path(points, base_y)
    line = line_path(points)

    max_week = max(counts) if counts else 0
    stops = gradient_stops(points, counts, width, padding_x, max_week)

    svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GitHub activity sparkline">
  <defs>
    <linearGradient id="sparkGradient" x1="{padding_x}" y1="0" x2="{width - padding_x}" y2="0" gradientUnits="userSpaceOnUse">
      {stops}
    </linearGradient>
  </defs>
  <line x1="{padding_x}" y1="{base_y}" x2="{width - padding_x}" y2="{base_y}" stroke="#30363d" stroke-width="0.8"/>
  <path d="{fill}" fill="#2ea043" fill-opacity="0.04"/>
  <path d="{line}" stroke="url(#sparkGradient)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>'''
    return svg

def get_weeks(refresh=False):
    if refresh:
        print("Fetching fresh GitHub contribution data...")
        all_weeks = [fetch_contributions(u) for u in GITHUB_USERNAMES]
        weeks = merge_contributions(all_weeks)
        weeks = last_n_weeks(weeks, 52)
        save_weeks(weeks)
        print(f"Saved activity data to {CACHE_PATH}")
        return weeks

    print(f"Loading cached activity data from {CACHE_PATH}")
    return load_weeks()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Fetch fresh contribution data from GitHub and cache it locally."
    )
    args = parser.parse_args()

    weeks = get_weeks(refresh=args.refresh)
    svg = build_svg(weeks)
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
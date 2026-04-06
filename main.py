import os
import requests
from pathlib import Path

GITHUB_TOKEN = os.environ['GH_TOKEN']
GITHUB_USERNAMES = [
    os.environ['GITHUB_USERNAME'],
    'markjrieke-fortisgames'
]

OUTPUT_PATH = Path('assets/activity-sparkline.svg')
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

class SVG:
    WIDTH = 240
    HEIGHT = 32
    PADDING_X = 3
    PADDING_TOP = 3
    PADDING_BOTTOM = 4
    BASELINE_COLOR = '#30363D'
    FILL_COLOR = '#2EA043'
    STROKE_WIDTH = 1.35
    COLOR_DARK = '#274029'
    COLOR_LIGHT = '#56D364'

svg = SVG()

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
        'https://api.github.com/graphql',
        json={'query': QUERY, 'variables': {'login': username}},
        headers={
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github+json'
        },
        timeout=30
    )
    response.raise_for_status()
    data = response.json()

    weeks = data['data']['user']['contributionsCollection']['contributionCalendar']['weeks']
    out = []
    for week in weeks:
        weekly_data = {
            'week_start': week['contributionDays'][0]['date'],
            'count': sum(day['contributionCount'] for day in week['contributionDays'])
        }
        out.append(weekly_data)

    return out

def merge_contributions(all_weeks_list):
    combined = {}
    for weeks in all_weeks_list:
        for week in weeks:
            key = week['week_start']
            if key in combined:
                combined['key']['count'] += week['count']
            else:
                combined['key'] = {
                    'week_start': key,
                    'count': week['count']
                }
    out = [combined[k] for k in sorted(combined)]

def last_n_weeks(weeks, n=26):
    return weeks[-n:] if weeks is not None else []

def scale_points(
    counts,
    width,
    height,
    padding_top,
    padding_bottom,
    padding_x
):
    n = len(counts)
    if n == 0:
        return []

    max_count = max(max(counts), 1)
    usable_w = width - 2 * padding_x
    usable_h = height - padding_top - padding_bottom

    points = []
    for i, c in enumerate(counts):
        x = padding_x + (usable_w * i / (n - 1 if n > 1 else 1))
        normalized = c / max_count
        y = padding_top + usable_h * (1 - normalized)
        points.append((x, y))

    return points

def quad_bezier(p0, p1):
    x0, y0 = p0
    x1, y1 = p1
    cx = (x0 + x1) / 2
    return f'Q {cx:.2f},{y0:.2f} {x1:.2f},{y1:.2f}'

def area_path(points, base_y):
    if len(points) < 2:
        return ''
    
    d = f'M {points[0][0]:.2f},{base_y:.2f} '
    d += f'L {points[0][0]:.2f},{points[0][1]:.2f} '

    for i in range(1, len(points)):
        d += quad_bezier(points[i-1], points[i]) + ' '

    d += f'L {points[-1][0]:.2f},{base_y:.2f} Z'

    return d

def hex_to_rgb(hex: str):
    h = hex.lstrip('#')
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return r, g, b

def lerp(value, lower, upper):
    return lower + value * (upper - lower)

def rgb_to_hex(rgb: tuple):
    r = rgb[0]
    g = rgb[1]
    b = rgb[2]
    return f'#{r:02x}{g:02x}{b:02x}'

def intensity_color(value, max_value):
    if max_value <= 0:
        return svg.COLOR_DARK
    ratio = value / max_value
    rd, gd, bd = hex_to_rgb(svg.COLOR_DARK)
    rb, gb, bb = hex_to_rgb(svg.COLOR_LIGHT)
    r = lerp(ratio, rd, rb)
    g = lerp(ratio, gd, gb)
    b = lerp(ratio, bd, bb)
    return rgb_to_hex((r, g, b))

def build_svg(weeks):
    counts = [w['count'] for w in weeks]
    points = scale_points(
        counts=counts,
        width=svg.WIDTH,
        height=svg.HEIGHT,
        padding_top=svg.PADDING_TOP,
        padding_bottom=svg.PADDING_BOTTOM,
        padding_x=svg.PADDING_X
    )

    base_y = svg.HEIGHT - svg.PADDING_BOTTOM
    fill = area_path(points, base_y)
    max_week = max(counts) if counts else 0

    segment_paths = []
    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        intensity = max(counts[i - 1], counts[i])
        color = intensity_color(intensity, max_week)
        curve = quad_bezier(points[i - 1], points[i])

        segment_paths.append(
            f'<path d="M {x0:.2f},{y0:.2f} {curve}" '
            f'stroke="{color}" stroke-width="{svg.STROKE_WIDTH}" '
            f'stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
        )
        
    segment_svg = '\n '.join(segment_paths)
    out = f'''
    <svg width="{svg.WIDTH}" height="{svg.HEIGHT} viewBox="0 0 {svg.WIDTH} {svg.HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Github activity sparkline">
        <line x1="{svg.PADDING_X}" y1="{base_y}" x2="{svg.WIDTH - svg.PADDING_X}" y2="{base_y}" stroke="{svg.BASELINE_COLOR}" stroke-width="0.8"/>
        <path d="{fill}" fill="{svg.FILL_COLOR}" fill-opacity="{svg.FILL_OPACITY}"/>
        {segment_svg}
    </svg>
    '''

    return out

def main():
    all_weeks = [fetch_contributions(u) for u in GITHUB_USERNAMES]
    merged = merge_contributions(all_weeks)
    recent = last_n_weeks(merged, 26)
    svg = build_svg(recent)
    OUTPUT_PATH.write_text(svg, encoding='utf-8')
    print(f'Wrote {OUTPUT_PATH}')

if __name__ == '__main__':
    main()
"""Generate profile SVGs from public GitHub data; no personal token required."""

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Python": "#3572a5",
    "HTML": "#e34c26", "CSS": "#563d7c", "SCSS": "#c6538c", "Java": "#b07219",
    "C++": "#f34b7d", "C": "#555555", "C#": "#178600", "Go": "#00add8",
    "Rust": "#dea584", "Shell": "#89e051", "Vue": "#41b883", "Svelte": "#ff3e00",
    "PHP": "#4f5d95", "Kotlin": "#a97bff", "Dart": "#00b4ab", "Other": "#8c959f",
}
EXTENSIONS = {
    ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript",
    ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".py": "Python", ".html": "HTML", ".htm": "HTML", ".css": "CSS",
    ".scss": "SCSS", ".java": "Java", ".cpp": "C++", ".cc": "C++",
    ".cxx": "C++", ".h": "C", ".c": "C", ".cs": "C#", ".go": "Go",
    ".rs": "Rust", ".sh": "Shell", ".vue": "Vue", ".svelte": "Svelte",
    ".php": "PHP", ".kt": "Kotlin", ".dart": "Dart",
}


def fetch(url, *, api=False):
    headers = {"User-Agent": "nguyen-github-profile", "Accept": "application/vnd.github+json" if api else "text/html"}
    if api and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with urlopen(Request(url, headers=headers), timeout=60) as response:
        content = response.read().decode("utf-8")
    return json.loads(content) if api else content


def pages(endpoint):
    result = []
    for page in range(1, 11):
        batch = fetch(f"https://api.github.com/{endpoint}?per_page=100&page={page}", api=True)
        result.extend(batch)
        if len(batch) < 100:
            break
    return result


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = {}
        self.counts = {}
        self.tooltip = None
        self.tooltip_text = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "data-date" in attrs:
            self.cells[attrs["id"]] = (attrs["data-date"], int(attrs["data-level"]))
        elif tag == "tool-tip":
            self.tooltip = attrs.get("for")
            self.tooltip_text = ""

    def handle_data(self, data):
        if self.tooltip:
            self.tooltip_text += data

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.tooltip:
            match = re.search(r"([\d,]+) contributions?", self.tooltip_text)
            self.counts[self.tooltip] = int(match[1].replace(",", "")) if match else 0
            self.tooltip = None

    def days(self, today):
        if not self.cells or any(key not in self.counts for key in self.cells):
            raise ValueError("GitHub contribution calendar format changed; keeping existing SVGs")
        return sorted((date, level, self.counts[key]) for key, (date, level) in self.cells.items() if date <= today)


def text(x, y, content, *, cls="body", anchor="start"):
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{escape(str(content))}</text>'


def svg(title, description, height, content):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="{height}" viewBox="0 0 480 {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>
<style>
text{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif;font-size:12px}}
.body{{fill:#57606a}}.heading{{fill:#0969da;font-size:15px}}.muted{{fill:#6e7781;font-size:10px}}
.surface{{fill:#ffffff}}.track{{fill:#eaeef2}}
@media(prefers-color-scheme:dark){{.surface{{fill:#0d1117}}.body{{fill:#c9d1d9}}.heading{{fill:#58a6ff}}.muted{{fill:#8b949e}}.track{{fill:#21262d}}}}
</style><rect width="480" height="{height}" class="surface"/>
{''.join(content)}
</svg>\n'''


def calendar_svg(days, *, half=False):
    if half:
        cutoff = (datetime.fromisoformat(days[-1][0]) - timedelta(days=179)).date().isoformat()
        days = [day for day in days if day[0] >= cutoff]
    first = datetime.fromisoformat(days[0][0]).date()
    first -= timedelta(days=(first.weekday() + 1) % 7)
    weeks = ((datetime.fromisoformat(days[-1][0]).date() - first).days // 7) + 1
    step = min(12, 365 / max(weeks - 1, 1))
    run = best = 0
    for _, _, count in days:
        run = run + 1 if count else 0
        best = max(best, run)
    current = run
    if not days[-1][2]:
        current = 0
        for _, _, count in reversed(days[:-1]):
            if not count:
                break
            current += 1
    total = sum(count for _, _, count in days)
    parts = [text(20, 30, "Contributions calendar", cls="heading"),
             text(260, 60, f"Best streak  {best} days"),
             text(260, 81, f"Current streak  {current} days"),
             text(260, 102, f"Highest in a day  {max(d[2] for d in days)}"),
             text(260, 123, f"Average per day  {total / len(days):.2f}")]
    palettes = [('#ebedf0', '#d8dee4', '#e1e6eb'), ('#9be9a8', '#70c783', '#80d492'),
                ('#40c463', '#2e994b', '#35ad55'), ('#30a14e', '#247a3b', '#288b42'),
                ('#216e39', '#174f29', '#1c6031')]
    for date, level, count in days:
        delta = (datetime.fromisoformat(date).date() - first).days
        week, weekday = divmod(delta, 7)
        x, y = 22 + week * step + weekday * 7, 152 + week * step * .48 - weekday * 4
        height = 0 if not count else 3 + level * 4
        top, left, right = palettes[level]
        parts.append(f'<g><title>{date}: {count} contributions</title>')
        if height:
            parts.append(f'<path fill="{left}" d="M{x-6},{y-height}l6,3v{height}l-6,-3z"/>')
            parts.append(f'<path fill="{right}" d="M{x},{y-height+3}l6,-3v{height}l-6,3z"/>')
        parts.append(f'<path fill="{top}" d="M{x},{y-height-3}l6,3l-6,3l-6,-3z"/></g>')
    parts += [text(20, 355, f"{total:,} contributions · {days[0][0]} — {days[-1][0]}", cls="muted")]
    return svg("Isometric contribution calendar", "Public GitHub contribution calendar with daily counts and streaks.", 375, parts)


def human_bytes(value):
    return f"{value / 1_000_000:.2f} MB" if value >= 1_000_000 else f"{value / 1000:.1f} kB" if value >= 1000 else f"{value} B"


def languages_svg(values, *, recent=False, note="", updated=""):
    entries = values.most_common(8)
    remainder = sum(values.values()) - sum(value for _, value in entries)
    if remainder:
        entries = values.most_common(7)
        entries.append(("Other", sum(values.values()) - sum(value for _, value in entries)))
    total = sum(values.values())
    title = "Recently used languages" if recent else "Most used languages"
    parts = [text(20, 30, f"{len(values)} languages", cls="heading"),
             text(240, 55, title, cls="heading", anchor="middle"),
             text(240, 73, note, cls="muted", anchor="middle"),
             '<rect x="20" y="85" width="440" height="8" rx="4" class="track"/>']
    if entries:
        parts.append('<defs><clipPath id="bar"><rect x="20" y="85" width="440" height="8" rx="4"/></clipPath></defs>')
        x = 20
        for language, value in entries:
            width = 440 * value / total
            color = COLORS.get(language, "#8c959f")
            parts.append(f'<rect x="{x:.3f}" y="85" width="{width:.3f}" height="8" fill="{color}" clip-path="url(#bar)"/>')
            x += width
        for index, (language, value) in enumerate(entries):
            x, y = 28 + (index % 2) * 224, 115 + (index // 2) * 27
            parts.append(f'<circle cx="{x}" cy="{y-4}" r="4" fill="{COLORS.get(language, "#8c959f")}"/>')
            parts.append(text(x + 12, y, language))
            amount = f"{value:,} lines" if recent else human_bytes(value)
            parts.append(text(x + 200, y, f"{amount} · {value / total:.1%}", cls="muted", anchor="end"))
    else:
        parts.append(text(240, 121, "No public code changes in this period", anchor="middle"))
    height = 140 + max(1, (len(entries) + 1) // 2) * 27
    parts.append(text(20, height - 12, f"Updated {updated} · public GitHub data", cls="muted"))
    return svg(title, note, height, parts)


def collect_recent(user, events, now):
    """Count added/deleted code lines in public push comparisons, by extension.

    This measures changed lines, not a Linguist in-depth author analysis.
    GitHub's comparison API returns at most 300 files per push.
    """
    counts = Counter()
    seen = set()
    pushes = 0
    capped = False
    for event in events:
        if event["type"] != "PushEvent" or event["actor"]["login"].lower() != user.lower():
            continue
        if datetime.fromisoformat(event["created_at"].replace("Z", "+00:00")) < now - timedelta(days=14):
            continue
        payload = event["payload"]
        before, head = payload.get("before"), payload.get("head")
        if not before or not head or before == "0" * 40:
            continue
        repo = event["repo"]["name"]
        key = (repo, before, head)
        if key in seen:
            continue
        seen.add(key)
        comparison = fetch(f"https://api.github.com/repos/{repo}/compare/{before}...{head}", api=True)
        files = comparison.get("files", [])
        capped |= len(files) >= 300
        pushes += 1
        for file in files:
            if "patch" not in file:  # Skip binary assets.
                continue
            language = EXTENSIONS.get(Path(file["filename"]).suffix.lower())
            if language:
                counts[language] += file["additions"] + file["deletions"]
    return +counts, pushes, capped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", default="trtrnguyen14104")
    args = parser.parse_args()
    user = quote(args.user, safe="")
    now = datetime.now(timezone(timedelta(hours=7)))
    today = now.date().isoformat()
    calendar = CalendarParser()
    calendar.feed(fetch(f"https://github.com/users/{user}/contributions"))
    days = calendar.days(today)
    if not days:
        raise ValueError("No contribution calendar data returned")
    repos = [repo for repo in pages(f"users/{user}/repos") if not repo["fork"]]
    languages = Counter()
    for repo in repos:
        languages.update(fetch(repo["languages_url"], api=True))
    languages = +languages
    events = pages(f"users/{user}/events/public")
    recent, pushes, capped = collect_recent(args.user, events, now)
    recent_note = f"Last 14 days · {pushes} public pushes · changed code lines"
    if capped:
        recent_note = "Last 14 days · first 300 files per push · changed lines"
    outputs = {
        "isocalendar-full-year.svg": calendar_svg(days),
        "isocalendar-half-year.svg": calendar_svg(days, half=True),
        "languages.svg": languages_svg(languages, note=f"{len(repos)} public source repositories · code size", updated=today),
        "languages-recent.svg": languages_svg(recent, recent=True, note=recent_note, updated=today),
    }
    destination = ROOT / "assets" / "metrics"
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        (destination / name).write_text(content, encoding="utf-8")
    print(f"Updated {len(outputs)} SVGs: {len(days)} days, {len(repos)} repositories, {len(languages)} languages, {pushes} recent pushes")


if __name__ == "__main__":
    main()

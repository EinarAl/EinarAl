#!/usr/bin/env python3
import os, sys, json, re, subprocess, tempfile, shutil, urllib.request
from datetime import datetime, timezone, date

CREATED = datetime(2021, 6, 23, 3, 42, 15, tzinfo=timezone.utc)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LANG_COLORS = {
    "TypeScript": "#3178c6",
    "C++": "#f34b7d",
    "Python": "#3572a5",
    "GLSL": "#5686a5",
    "Html": "#e34c26",
    "CSS": "#563d7c",
    "JS": "#f1e05a",
}

ME1_PATH = os.path.join(ROOT, "me1.txt")
RIGHT_X = 15
Y_START = 30
Y_STEP = 20

def api(path):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    h = {"Accept": "application/vnd.github+json", "User-Agent": "profile-updater"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"https://api.github.com{path}", headers=h)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def gql(query):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-updater"}
    req = urllib.request.Request("https://api.github.com/graphql", headers=h, data=json.dumps({"query": query}).encode())
    return json.loads(urllib.request.urlopen(req).read())

def get_contributions():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        return 0, 0
    commits = 0
    start = CREATED.year
    now = datetime.now(timezone.utc)
    for y in range(start, now.year + 1):
        q = f'query{{user(login:"EinarAl"){{contributionsCollection(from:"{y}-01-01T00:00:00Z",to:"{y}-12-31T23:59:59Z"){{totalCommitContributions restrictedContributionsCount}}}}}}'
        try:
            resp = gql(q)
            d = resp["data"]["user"]["contributionsCollection"]
            total = d.get("totalCommitContributions") or 0
            restricted = d.get("restrictedContributionsCount") or 0
            commits += max(total - restricted, 0)
        except:
            pass
    try:
        prs = api("/search/issues?q=author:EinarAl+type:pr+is:merged&per_page=1")["total_count"]
    except:
        prs = 0
    return commits, prs

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

EXCLUDED_LOC = (
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Cargo.lock", "go.sum", "Gemfile.lock", "composer.lock",
)
BINARY_EXT = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".pdf", ".zip",
    ".gz", ".tar", ".mp3", ".mp4", ".webm", ".wasm", ".bin", ".db",
)

def count_loc(repo_dir):
    total = 0
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=repo_dir, capture_output=True, text=True, errors="replace").stdout
        for rel in out.split("\0"):
            if not rel:
                continue
            base = os.path.basename(rel)
            if base in EXCLUDED_LOC or base.endswith(".lock") or base.endswith(BINARY_EXT):
                continue
            parts = rel.replace("/", os.sep).split(os.sep)
            if any(p in ("node_modules", "dist", "build", ".next", "out", "coverage", "vendor", "target", ".git") for p in parts):
                continue
            path = os.path.join(repo_dir, rel.replace("/", os.sep))
            try:
                with open(path, "rb") as fh:
                    for raw in fh:
                        if raw.decode("utf-8", errors="ignore").strip():
                            total += 1
            except OSError:
                pass
    except Exception:
        pass
    return total

def sum_numstat(repo_dir):
    added = 0
    deleted = 0
    try:
        out = subprocess.run(["git", "log", "--pretty=tformat:", "--numstat"], cwd=repo_dir, capture_output=True, text=True, errors="replace").stdout
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                added += int(parts[0])
                deleted += int(parts[1])
    except Exception:
        pass
    return added, deleted

def get_loc_data():
    try:
        repos = api("/users/EinarAl/repos?per_page=100&sort=pushed")
    except:
        return 0, 0, 0
    tmp = tempfile.mkdtemp(prefix="profile_loc_")
    loc = 0
    add = 0
    delete = 0
    try:
        for r in repos:
            if r.get("fork"):
                continue
            name = r["name"]
            dest = os.path.join(tmp, name)
            try:
                subprocess.run(["git", "clone", "--quiet", r["clone_url"], dest], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                continue
            loc += count_loc(dest)
            a, d = sum_numstat(dest)
            add += a
            delete += d
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return loc, add, delete

def get_stats():
    user = api("/users/EinarAl")
    total = user["public_repos"]
    commits, prs = get_contributions()
    now = datetime.now(timezone.utc)
    d = (now.date() - CREATED.date()).days
    uptime = f"{d//365} yrs, {(d%365)//30} mo, {(d%365)%30} days"
    loc, loc_add, loc_del = get_loc_data()
    return {
        "__UPTIME__": uptime,
        "__REPOS__": str(total),
        "__COMMITS__": str(commits),
        "__PRS__": str(prs),
        "__LOC__": f"{loc:,}",
        "__LOC_ADD__": f"{loc_add:,}",
        "__LOC_DEL__": f"{loc_del:,}",
    }

def process_panel_dots(text):
    text = text.replace("*", "\u2022")
    result = ""
    remaining = text
    while remaining:
        best_pos = len(remaining)
        best_name = None
        for name in LANG_COLORS:
            marker = f"\u2022 {name}"
            pos = remaining.find(marker)
            if pos >= 0 and pos < best_pos:
                best_pos = pos
                best_name = name
        if best_name:
            result += esc(remaining[:best_pos])
            result += f'<tspan fill="{LANG_COLORS[best_name]}">\u25cf</tspan>{esc(best_name)}'
            remaining = remaining[best_pos + len(f"\u2022 {best_name}"):]
        else:
            result += esc(remaining)
            break
    return result

TARGET = 58

def visual_len(text, stats):
    v = text
    for k, val in stats.items():
        v = v.replace(k, val)
    return len(re.sub(r'<[^>]+>', '', process_panel_dots(v)))

def make_dots_line(prefix, key, raw_val, right_x, y, stats, target_adjust=0):
    est_len = visual_len(raw_val, stats)
    dots_needed = TARGET + target_adjust - len(prefix) - len(key) - 2 - est_len
    if dots_needed < 1:
        dots_needed = 1
    dots_str = "." * dots_needed
    processed_val = process_panel_dots(raw_val)
    return (
        f'<text x="{right_x}" y="{y}" class="n" xml:space="preserve">'
        f'<tspan class="d">{esc(prefix)}</tspan>'
        f'<tspan class="k">{esc(key)}</tspan>'
        f'<tspan class="d">{esc(":" + dots_str + " ")}</tspan>'
        f'<tspan class="v">{processed_val}</tspan>'
        f'</text>'
    )

def build_svg_content(lines, stats):
    left_parts = []
    right_parts = []

    for i, line in enumerate(lines):
        y = Y_START + i * Y_STEP

        if "\t" in line:
            left = line.split("\t")[0]
            right = line.split("\t")[-1]
        else:
            left = ""
            right = line

        if left.strip():
            left_parts.append(f'<text x="{RIGHT_X}" y="{y}" class="a" xml:space="preserve">{esc(left)}</text>')

        right = right.strip()
        if not right or right == ".":
            right_parts.append(f'<text x="{RIGHT_X}" y="{y}" class="d" xml:space="preserve"></text>')
        elif right.startswith("user@"):
            di = right.find("-")
            if di < 0: di = len(right)
            prefix = right[:di]
            nd = TARGET - len(prefix)
            if nd < 1: nd = 1
            right_parts.append(f'<text x="{RIGHT_X}" y="{y}" class="h" xml:space="preserve">{esc(prefix)}{"-" * nd}</text>')
        elif "---" in right or "===" in right:
            for sep in ["---", "==="]:
                if sep in right:
                    idx = right.index(sep)
                    name = right[:idx].strip().strip(".").strip()
                    break
            nd = TARGET - len(name) - 1
            if nd < 1: nd = 1
            if name:
                content = f'<tspan class="k">{esc(name)}</tspan><tspan class="k"> {"-" * nd}</tspan>'
            else:
                content = f'<tspan class="k">{"-" * TARGET}</tspan>'
            right_parts.append(f'<text x="{RIGHT_X}" y="{y}" class="n" xml:space="preserve">{content}</text>')
        elif right.startswith("..."):
            ci = 0
            while ci < len(right) and right[ci] in ". ":
                ci += 1
            raw_content = right[ci:]
            content_len = visual_len(raw_content, stats)
            orig_leading = right[:ci]
            margin = len(orig_leading) - len(orig_leading.rstrip(" "))
            if margin < 1: margin = 2
            pad = TARGET - content_len
            if pad < 0: pad = 0
            dots = pad - margin
            if dots < 0: dots = 0
            leading = "." * dots + " " * margin
            right_parts.append(
                f'<text x="{RIGHT_X}" y="{y}" class="n" xml:space="preserve">'
                f'<tspan class="d">{esc(leading)}</tspan>'
                f'<tspan class="v">{process_panel_dots(raw_content)}</tspan>'
                f'</text>'
            )
        elif right.startswith(".."):
            colon = right.find(":", 2)
            if colon > 0:
                key = right[2:colon].strip()
                raw_val = right[colon + 1:].lstrip(". ")
                right_parts.append(make_dots_line(".. ", key, raw_val, RIGHT_X, y, stats))
            else:
                right_parts.append(f'<text x="{RIGHT_X}" y="{y}" class="v" xml:space="preserve">{process_panel_dots(right)}</text>')
        elif right.startswith(". "):
            colon = right.find(":", 2)
            if colon > 0:
                key = right[2:colon].strip()
                raw_val = right[colon + 1:].lstrip(". ")
                target_adjust = -1 if key == "Human Languages" else 0
                right_parts.append(make_dots_line(". ", key, raw_val, RIGHT_X, y, stats, target_adjust))
            else:
                right_parts.append(f'<text x="{RIGHT_X}" y="{y}" class="v" xml:space="preserve">{process_panel_dots(right)}</text>')
        else:
            right_parts.append(f'<text x="{RIGHT_X}" y="{y}" class="n" xml:space="preserve">{esc(right)}</text>')

    return "".join(left_parts) + "".join(right_parts)

def main():
    stats = get_stats()
    lines = open(ME1_PATH, encoding="utf-8").read().splitlines()
    content = build_svg_content(lines, stats)

    for k, v in stats.items():
        content = content.replace(k, v)

    # Color N++ green and N-- red
    content = re.sub(r'(\d[\d,]*)\+\+', r'<tspan class="add">\1++</tspan>', content)
    content = re.sub(r'(\d[\d,]*)--', r'<tspan class="del">\1--</tspan>', content)

    for theme in ("dark", "light"):
        t_path = os.path.join(ROOT, f"{theme}_mode_template.svg")
        o_path = os.path.join(ROOT, f"{theme}_mode.svg")
        if os.path.exists(t_path):
            tmpl = open(t_path, encoding="utf-8").read()
            tmpl = tmpl.replace("__SVG_CONTENT__", content)
            open(o_path, "w", encoding="utf-8").write(tmpl)
            sys.stderr.write(f"Written {o_path}\n")

    # Update README with agent-readable stats block + cache-bust timestamp
    readme_path = os.path.join(ROOT, "README.md")
    if os.path.exists(readme_path):
        readme = open(readme_path, encoding="utf-8").read()
        profile_data = {
            "repos": int(stats["__REPOS__"]),
            "commits": int(stats["__COMMITS__"]),
            "prs": int(stats["__PRS__"]),
            "loc": int(stats["__LOC__"].replace(",", "")),
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "links": [
                "https://github.com/EinarAl",
                "https://monoscript-studio.vercel.app",
                "https://chladni-tuner.vercel.app",
            ],
        }
        block = f"<!-- PROFILE-DATA\n{json.dumps(profile_data, separators=(',', ':'))}\n-->\n"
        readme = re.sub(r"<!-- PROFILE-DATA.*?-->\s*", "", readme, flags=re.S)
        readme = block + readme
        ts = int(datetime.now().timestamp())
        readme = re.sub(r'(dark_mode\.svg)(\?v=\d+)?', rf'\1?v={ts}', readme)
        readme = re.sub(r'(light_mode\.svg)(\?v=\d+)?', rf'\1?v={ts}', readme)
        open(readme_path, "w", encoding="utf-8").write(readme)
        sys.stderr.write(f"Updated {readme_path} with PROFILE-DATA + cache-bust\n")

if __name__ == "__main__":
    main()

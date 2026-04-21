import csv
import io
import os
import json
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from urllib.parse import quote

with open(os.path.join(os.path.dirname(__file__), "repos.json")) as _f:
    WATCHED_REPOS = json.load(_f)

_raw_user_configs = os.environ.get("USER_CONFIGS", "")
if _raw_user_configs:
    USER_CONFIGS = json.loads(_raw_user_configs)
else:
    # Fallback: single user from individual env vars
    USER_CONFIGS = [{
        "email": os.environ.get("NOTIFY_EMAIL") or "namanworkie@gmail.com",
        "name": os.environ.get("NOTIFY_NAME") or "User",
        "max_issues": int(os.environ.get("MAX_ISSUES") or 5),
        "difficulty_min": int(os.environ.get("DIFFICULTY_MIN") or 1),
        "difficulty_max": int(os.environ.get("DIFFICULTY_MAX") or 7),
        "areas": [a.strip() for a in (os.environ.get("AREAS") or "").split(",") if a.strip()] or [],
    }]

# Build repo → areas lookup from repos.json
REPO_AREAS = {f"{r['owner']}/{r['repo']}": r.get("areas", []) for r in WATCHED_REPOS}

GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-2.0-flash"

# Maps GitHub label text → difficulty level 1-10 (from open_source_tags_scraped_difficulty)
LABEL_DIFFICULTY = {
    # L1 — first-timer only
    "good first issue": 1, "first-timers-only": 1, "good-first-pr": 1,
    "good-first-contribution": 1, "first time contributor": 1,
    "status: first-timers-only": 1, "status: ideal-for-contribution": 1,
    "status: ideal-for-user-contribution": 1, "info: good first issue": 1,
    "Good First Issue": 1, "Good first issue": 1, "good first issue 👍": 1,
    # L2 — beginner-friendly
    "beginner": 2, "beginner-friendly": 2, "starter": 2,
    "low-hanging-fruit": 2, "easy": 2,
    # L3 — documentation
    "documentation": 3, "docs": 3, "examples": 3, "readme": 3,
    # L4 — help wanted / up for grabs
    "help wanted": 4, "up-for-grabs": 4, "up for grabs": 4,
    "contributions-welcome": 4, "contributions welcome": 4,
    "accepting-prs": 4, "please contribute": 4,
    "status: good-first-issue": 4, "s: pull request welcome": 4,
    "starter task": 4, "type/good-first-issue": 4,
    # L5 — hacktoberfest
    "hacktoberfest": 5, "hacktoberfest-accepted": 5, "good-first-project": 5,
    # L6 — bug / enhancement
    "bug": 6, "enhancement": 6, "feature request": 6, "question": 6,
    # L7 — refactor / tech debt
    "refactoring": 7, "tech-debt": 7, "cleanup": 7, "code-quality": 7,
    # L8 — triage
    "needs-triage": 8, "needs-investigation": 8,
    # L9 — performance / security
    "performance": 9, "performance-boost": 9, "security": 9,
    "vulnerability": 9, "memory-leak": 9,
    # L10 — core / architecture
    "core": 10, "internals": 10, "breaking-change": 10,
    "RFC": 10, "major-feature": 10, "expert-needed": 10,
}

GEMINI_PROMPT = """You are an expert open source contributor advisor helping a backend Java/SRE developer find the best issues to contribute to.

For each GitHub issue below, provide:
1. score (1-10): overall contribution worthiness for a backend/SRE developer
   - 10 = perfect fit: approachable, impactful, matches Java/SRE skills, active repo
   - 1 = poor fit: too hard, stale, or irrelevant
   Weigh: approachability (40%), SRE/backend relevance (30%), impact/visibility (30%)
2. what_to_do: 1-2 sentences describing concretely what code changes are needed to resolve the issue

Return ONLY a valid CSV — no markdown fences, no explanation, no preamble.
Use this exact header row:
repo,issue_number,title,url,labels,created,score,what_to_do

Rules:
- Wrap any field containing commas in double-quotes
- Escape internal double-quotes by doubling them ("")
- One row per issue, same order as input
- score must be an integer 1-10

Issues to analyze (JSON):
{issues_json}"""


def fetch_issues(owner, repo, label, token=None):
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/issues"
        f"?labels={quote(label, safe='')}&state=open&sort=created&direction=desc&per_page=20"
    )
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "oss-issue-watcher"}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        req = Request(url, headers=headers)
        with urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        print(f"  ERROR fetching {owner}/{repo} label='{label}': HTTP {e.code}")
        return []


def load_seen_issues(filepath="seen_issues.json"):
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_issues(seen, filepath="seen_issues.json"):
    with open(filepath, "w") as f:
        json.dump(sorted(list(seen)), f)


def get_label_difficulty(labels):
    """Return lowest (easiest) difficulty from issue labels, defaulting to 4."""
    difficulties = [LABEL_DIFFICULTY[l] for l in labels if l in LABEL_DIFFICULTY]
    return min(difficulties) if difficulties else 4


GEMINI_BATCH_SIZE = 150


def _call_gemini(api_key, batch):
    """Single Gemini API call for one batch. Returns cleaned CSV text."""
    issues_json = json.dumps([
        {
            "repo": i["repo"],
            "issue_number": i["number"],
            "title": i["title"],
            "url": i["url"],
            "labels": ", ".join(i["labels"]),
            "created": i["created"],
        }
        for i in batch
    ], indent=2)

    prompt = GEMINI_PROMPT.format(issues_json=issues_json)
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 65536},
    }).encode()

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )
    req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urlopen(req) as resp:
        result = json.loads(resp.read().decode())
    csv_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    if csv_text.startswith("```"):
        csv_text = "\n".join(
            line for line in csv_text.splitlines() if not line.startswith("```")
        ).strip()
    return csv_text


def analyze_with_gemini(issues):
    """Send all issues to Gemini in batches of 150. Returns combined CSV string or None."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set — skipping analysis.")
        return None

    batches = [issues[i:i + GEMINI_BATCH_SIZE] for i in range(0, len(issues), GEMINI_BATCH_SIZE)]
    print(f"Sending {len(issues)} issues to Gemini in {len(batches)} batch(es)...")

    header = None
    all_rows = []

    for idx, batch in enumerate(batches):
        try:
            csv_text = _call_gemini(api_key, batch)
            lines = [l for l in csv_text.splitlines() if l.strip()]
            if not lines:
                continue
            if header is None:
                header = lines[0]
                all_rows.extend(lines[1:])
            else:
                data_lines = lines[1:] if lines[0] == header else lines
                all_rows.extend(data_lines)
            print(f"  Batch {idx + 1}/{len(batches)} done ({len(lines) - 1} rows)")
        except Exception as e:
            print(f"  ERROR on batch {idx + 1}: {e}")

    if header is None:
        return None

    combined = "\n".join([header] + all_rows)
    print(f"Gemini analysis complete — {len(all_rows)} rows scored")
    return combined


def parse_gemini_csv(csv_text):
    """Parse Gemini CSV into {url: {score, what_to_do}} dict."""
    result = {}
    if not csv_text:
        return result
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        for row in reader:
            url = row.get("url", "").strip()
            if not url:
                continue
            try:
                score = int(float(row.get("score", 0)))
            except (ValueError, TypeError):
                score = 0
            result[url] = {
                "score": score,
                "what_to_do": row.get("what_to_do", "").strip(),
            }
    except Exception as e:
        print(f"ERROR parsing Gemini CSV: {e}")
    return result


def filter_issues_for_user(issues, user, gemini_scores):
    """Filter and rank issues per user's difficulty range, areas, and max_issues cap."""
    diff_min = user.get("difficulty_min", 1)
    diff_max = user.get("difficulty_max", 10)
    user_areas = [a.lower() for a in user.get("areas", [])]
    max_issues = user.get("max_issues", 5)

    filtered = []
    for issue in issues:
        score = gemini_scores.get(issue["url"], {}).get("score") or issue["difficulty"]

        if not (diff_min <= score <= diff_max):
            continue

        if user_areas:
            issue_areas = [a.lower() for a in issue.get("areas", [])]
            if not any(a in issue_areas for a in user_areas):
                continue

        filtered.append({**issue, "final_score": score})

    filtered.sort(key=lambda i: (i["final_score"], i["created"]), reverse=True)
    return filtered[:max_issues]


def build_user_csv(filtered_issues, gemini_scores):
    """Build a CSV string for a user's filtered issues including Gemini summary."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["repo", "issue_number", "title", "url", "labels", "areas", "created", "score", "what_to_do"])
    for issue in filtered_issues:
        g = gemini_scores.get(issue["url"], {})
        writer.writerow([
            issue["repo"],
            issue["number"],
            issue["title"],
            issue["url"],
            ", ".join(issue["labels"]),
            ", ".join(issue.get("areas", [])),
            issue["created"],
            g.get("score") or issue["difficulty"],
            g.get("what_to_do") or "—",
        ])
    return output.getvalue()


def build_email_html(filtered_issues, gemini_scores, user_name=None, total_found=0):
    rows = ""
    for issue in filtered_issues:
        label_badges = " ".join(
            f'<span style="background:#28a745;color:white;padding:2px 8px;border-radius:12px;font-size:11px;">{l}</span>'
            for l in issue["labels"]
        )
        area_badges = " ".join(
            f'<span style="background:#0366d6;color:white;padding:2px 8px;border-radius:12px;font-size:11px;">{a}</span>'
            for a in issue.get("areas", [])
        )
        score = gemini_scores.get(issue["url"], {}).get("score") or issue["difficulty"]
        score_color = "#28a745" if score >= 7 else "#e36209" if score >= 4 else "#586069"
        what_to_do = gemini_scores.get(issue["url"], {}).get("what_to_do", "")
        rows += f"""
        <tr style="border-bottom:1px solid #eee;">
            <td style="padding:12px;">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                    <span style="background:{score_color};color:white;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;">
                        ★ {score}/10
                    </span>
                    <strong><a href="{issue['url']}" style="color:#0366d6;text-decoration:none;">{issue['title']}</a></strong>
                </div>
                <span style="color:#586069;font-size:12px;">{issue['repo']}</span><br>
                <div style="margin-top:4px;">{label_badges} {area_badges}</div>
                {"<p style='color:#444;font-size:12px;margin:6px 0 0;font-style:italic;'>" + what_to_do + "</p>" if what_to_do else ""}
            </td>
            <td style="padding:12px;color:#586069;font-size:12px;white-space:nowrap;vertical-align:top;">
                {issue['created']}
            </td>
        </tr>
        """

    greeting = f"Hi {user_name}," if user_name else "Hi,"
    return f"""
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;">
        <h2 style="color:#24292e;">🚀 Your OSS Issues for Today</h2>
        <p style="color:#586069;">{greeting} Found <strong>{len(filtered_issues)}</strong> issues matching your preferences (from {total_found} new total). Full analysis attached as CSV.</p>
        <table style="width:100%;border-collapse:collapse;">
            <tr style="background:#f6f8fa;border-bottom:2px solid #e1e4e8;">
                <th style="padding:10px;text-align:left;">Issue</th>
                <th style="padding:10px;text-align:left;">Created</th>
            </tr>
            {rows}
        </table>
        <p style="color:#586069;font-size:12px;margin-top:20px;">
            Tip: Comment on the issue quickly to claim it. See <a href="https://github.com/NamanKu-tech/oss-issue-watcher/blob/main/CLAIMING_ISSUES.md">CLAIMING_ISSUES.md</a> for the full workflow.<br>
            Sent by OSS Issue Watcher • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
        </p>
    </body>
    </html>
    """


def send_email(subject, html_body, recipient, csv_attachment=None):
    sender = os.environ.get("SMTP_USERNAME") or "namanmahit@gmail.com"
    password = os.environ.get("SMTP_PASSWORD")

    if not all([sender, password, recipient]):
        print(f"ERROR: Missing email config for {recipient}.")
        return False

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"OSS Issue Watcher <{sender}>"
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    if csv_attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(csv_attachment.encode())
        encoders.encode_base64(part)
        filename = f"issues_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.csv"
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, [recipient], msg.as_string())
        print(f"Email sent to {recipient}")
        return True
    except Exception as e:
        print(f"ERROR sending email to {recipient}: {e}")
        return False


def main():
    token = os.environ.get("GH_TOKEN")
    seen = load_seen_issues()
    new_issues = []

    # Only scrape repos relevant to at least one user's area preferences
    all_user_areas = {a.lower() for user in USER_CONFIGS for a in user.get("areas", [])}
    if all_user_areas:
        active_repos = [
            r for r in WATCHED_REPOS
            if not r.get("areas") or any(a.lower() in all_user_areas for a in r["areas"])
        ]
    else:
        active_repos = WATCHED_REPOS

    print(f"Loaded {len(seen)} previously seen issues")
    print(f"Checking {len(active_repos)}/{len(WATCHED_REPOS)} repos (filtered to user areas)...\n")

    for config in active_repos:
        owner = config["owner"]
        repo = config["repo"]
        repo_key = f"{owner}/{repo}"
        for label in config["labels"]:
            print(f"Checking {repo_key} — label: '{label}'")
            issues = fetch_issues(owner, repo, label, token)
            print(f"  Found {len(issues)} open issue(s)")

            for issue in issues:
                if "pull_request" in issue:
                    continue
                issue_id = str(issue["id"])
                if issue_id not in seen:
                    seen.add(issue_id)
                    labels = [l["name"] for l in issue.get("labels", [])]
                    new_issues.append({
                        "title": issue["title"],
                        "url": issue["html_url"],
                        "repo": repo_key,
                        "labels": labels,
                        "areas": REPO_AREAS.get(repo_key, []),
                        "created": issue["created_at"][:10],
                        "number": issue["number"],
                        "difficulty": get_label_difficulty(labels),
                    })
                    print(f"  🆕 NEW: #{issue['number']} — {issue['title']}")

    print(f"\n{'='*50}")
    print(f"Total new issues found: {len(new_issues)}")

    if not new_issues:
        print("No new issues. No email sent.")
        save_seen_issues(seen)
        print("Saved seen issues list.")
        return

    raw_csv = analyze_with_gemini(new_issues)
    gemini_scores = parse_gemini_csv(raw_csv) if raw_csv else {}

    for user in USER_CONFIGS:
        filtered = filter_issues_for_user(new_issues, user, gemini_scores)
        name = user.get("name", user["email"])
        print(f"\nUser {name}: {len(filtered)} issues matched (difficulty {user.get('difficulty_min',1)}-{user.get('difficulty_max',10)}, areas: {user.get('areas',[])})")

        if not filtered:
            print(f"  No matching issues — skipping email.")
            continue

        user_csv = build_user_csv(filtered, gemini_scores)
        html = build_email_html(filtered, gemini_scores, user_name=user.get("name"), total_found=len(new_issues))
        subject = f"🚀 {len(filtered)} OSS issue{'s' if len(filtered) > 1 else ''} matched for you!"
        send_email(subject, html, recipient=user["email"], csv_attachment=user_csv)

    save_seen_issues(seen)
    print("\nSaved seen issues list.")


if __name__ == "__main__":
    main()

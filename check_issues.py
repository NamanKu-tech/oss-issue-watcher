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

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

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
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "oss-issue-watcher",
    }
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


def analyze_with_gemini(issues):
    """Send issues to Gemini for analysis. Returns CSV string or None."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set — skipping analysis.")
        return None

    issues_json = json.dumps([
        {
            "repo": i["repo"],
            "issue_number": i["number"],
            "title": i["title"],
            "url": i["url"],
            "labels": ", ".join(i["labels"]),
            "created": i["created"],
        }
        for i in issues
    ], indent=2)

    prompt = GEMINI_PROMPT.format(issues_json=issues_json)
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
    }).encode()

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )
    req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req) as resp:
            result = json.loads(resp.read().decode())
        csv_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Strip markdown fences if the model adds them anyway
        if csv_text.startswith("```"):
            csv_text = "\n".join(
                line for line in csv_text.splitlines()
                if not line.startswith("```")
            ).strip()
        print(f"Gemini analysis complete ({len(csv_text)} chars)")
        return csv_text
    except Exception as e:
        print(f"ERROR calling Gemini: {e}")
        return None


def send_email(subject, html_body, csv_attachment=None):
    sender = os.environ.get("SMTP_USERNAME", "namanmahit@gmail.com")
    password = os.environ.get("SMTP_PASSWORD")
    recipients_raw = os.environ.get("NOTIFY_EMAIL", "namanworkie@gmail.com")
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    if not all([sender, password, recipients]):
        print("ERROR: Missing email configuration. Set SMTP_USERNAME, SMTP_PASSWORD, NOTIFY_EMAIL.")
        return False

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"OSS Issue Watcher <{sender}>"
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))

    if csv_attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(csv_attachment.encode())
        encoders.encode_base64(part)
        filename = f"issues_analysis_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.csv"
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
        print(f"Email sent to {', '.join(recipients)}")
        return True
    except Exception as e:
        print(f"ERROR sending email: {e}")
        return False


def build_email_html(new_issues, has_csv=False):
    rows = ""
    for issue in new_issues:
        label_badges = " ".join(
            f'<span style="background:#28a745;color:white;padding:2px 8px;border-radius:12px;font-size:12px;">{l}</span>'
            for l in issue["labels"]
        )
        rows += f"""
        <tr style="border-bottom:1px solid #eee;">
            <td style="padding:12px;">
                <strong><a href="{issue['url']}" style="color:#0366d6;text-decoration:none;">
                    {issue['title']}
                </a></strong><br>
                <span style="color:#586069;font-size:13px;">{issue['repo']}</span><br>
                {label_badges}
            </td>
            <td style="padding:12px;color:#586069;font-size:13px;white-space:nowrap;">
                {issue['created']}
            </td>
        </tr>
        """

    attachment_note = (
        '<p style="color:#0366d6;font-size:13px;background:#f1f8ff;padding:10px;border-radius:6px;">'
        '📎 Gemini AI analysis attached as CSV — includes difficulty, estimated hours, skills required, SRE relevance, and recommendations.</p>'
        if has_csv else ""
    )

    return f"""
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;">
        <h2 style="color:#24292e;">🚀 New Open Source Contribution Opportunities</h2>
        <p style="color:#586069;">Found {len(new_issues)} new issue(s) matching your watched labels.</p>
        {attachment_note}
        <table style="width:100%;border-collapse:collapse;">
            <tr style="background:#f6f8fa;border-bottom:2px solid #e1e4e8;">
                <th style="padding:10px;text-align:left;">Issue</th>
                <th style="padding:10px;text-align:left;">Created</th>
            </tr>
            {rows}
        </table>
        <p style="color:#586069;font-size:12px;margin-top:20px;">
            Tip: Comment on the issue quickly to claim it before others do!<br>
            Sent by <a href="https://github.com">OSS Issue Watcher</a> • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
        </p>
    </body>
    </html>
    """


def main():
    token = os.environ.get("GH_TOKEN")
    seen = load_seen_issues()
    new_issues = []

    print(f"Loaded {len(seen)} previously seen issues")
    print(f"Checking {len(WATCHED_REPOS)} repos...\n")

    for config in WATCHED_REPOS:
        owner = config["owner"]
        repo = config["repo"]
        for label in config["labels"]:
            print(f"Checking {owner}/{repo} — label: '{label}'")
            issues = fetch_issues(owner, repo, label, token)
            print(f"  Found {len(issues)} open issue(s)")

            for issue in issues:
                if "pull_request" in issue:
                    continue

                issue_id = str(issue["id"])
                if issue_id not in seen:
                    seen.add(issue_id)
                    new_issues.append({
                        "title": issue["title"],
                        "url": issue["html_url"],
                        "repo": f"{owner}/{repo}",
                        "labels": [l["name"] for l in issue.get("labels", [])],
                        "created": issue["created_at"][:10],
                        "number": issue["number"],
                    })
                    print(f"  🆕 NEW: #{issue['number']} — {issue['title']}")

    print(f"\n{'='*50}")
    print(f"Total new issues found: {len(new_issues)}")

    if new_issues:
        csv_data = analyze_with_gemini(new_issues)
        subject = f"🚀 {len(new_issues)} new OSS contribution opportunity{'s' if len(new_issues) > 1 else ''}!"
        html = build_email_html(new_issues, has_csv=bool(csv_data))
        send_email(subject, html, csv_attachment=csv_data)
    else:
        print("No new issues. No email sent.")

    save_seen_issues(seen)
    print("Saved seen issues list.")


if __name__ == "__main__":
    main()

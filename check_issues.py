import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from urllib.parse import quote

with open(os.path.join(os.path.dirname(__file__), "repos.json")) as _f:
    WATCHED_REPOS = json.load(_f)


def fetch_issues(owner, repo, label, token=None):
    """Fetch open issues with a specific label from GitHub API."""
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
    """Load previously seen issue IDs."""
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_issues(seen, filepath="seen_issues.json"):
    """Save seen issue IDs."""
    with open(filepath, "w") as f:
        json.dump(sorted(list(seen)), f)


def send_email(subject, html_body):
    """Send email notification via SMTP (Gmail)."""
    sender = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    recipient = os.environ.get("NOTIFY_EMAIL")

    if not all([sender, password, recipient]):
        print("ERROR: Missing email configuration. Set SMTP_USERNAME, SMTP_PASSWORD, NOTIFY_EMAIL.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"OSS Issue Watcher <{sender}>"
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        print(f"Email sent to {recipient}")
        return True
    except Exception as e:
        print(f"ERROR sending email: {e}")
        return False


def build_email_html(new_issues):
    """Build a nicely formatted HTML email."""
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

    return f"""
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;">
        <h2 style="color:#24292e;">🚀 New Open Source Contribution Opportunities</h2>
        <p style="color:#586069;">Found {len(new_issues)} new issue(s) matching your watched labels.</p>
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
                # Skip pull requests (GitHub API returns PRs in issues endpoint)
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
        subject = f"🚀 {len(new_issues)} new OSS contribution opportunity{'s' if len(new_issues) > 1 else ''}!"
        html = build_email_html(new_issues)
        send_email(subject, html)
    else:
        print("No new issues. No email sent.")

    save_seen_issues(seen)
    print("Saved seen issues list.")


if __name__ == "__main__":
    main()

import os
import json
import smtplib
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import HTTPError

# ─── CONFIGURE YOUR WATCHED REPOS HERE ───
WATCHED_REPOS = [
    # ── Spring Ecosystem ──────────────────────────────────────────────────────
    {
        "owner": "spring-projects",
        "repo": "spring-boot",
        "labels": ["status: first-timers-only", "status: ideal-for-contribution"],
    },
    {
        "owner": "spring-projects",
        "repo": "spring-kafka",
        "labels": ["status: ideal-for-user-contribution"],
    },
    # ── Kafka / Messaging ─────────────────────────────────────────────────────
    {
        "owner": "kafbat",
        "repo": "kafka-ui",
        "labels": ["good first issue"],
    },
    {
        "owner": "tchiotludo",
        "repo": "akhq",
        "labels": ["good first issue"],
    },
    {
        "owner": "apache",
        "repo": "dubbo",
        "labels": ["good first issue"],
    },
    # ── Testing ───────────────────────────────────────────────────────────────
    {
        "owner": "testcontainers",
        "repo": "testcontainers-java",
        "labels": ["good first issue"],
    },
    # ── Auth / Identity ───────────────────────────────────────────────────────
    {
        "owner": "keycloak",
        "repo": "keycloak",
        "labels": ["good first issue"],
    },
    {
        "owner": "JanssenProject",
        "repo": "jans",
        "labels": ["good first issue"],
    },
    # ── Change Data Capture / Streaming ───────────────────────────────────────
    {
        "owner": "debezium",
        "repo": "debezium",
        "labels": ["good first issue"],
    },
    {
        "owner": "seata",
        "repo": "seata",
        "labels": ["first-time contributor","good first issue"],
    },
    # ── Cloud Native / Microservices ──────────────────────────────────────────
    {
        "owner": "quarkusio",
        "repo": "quarkus",
        "labels": ["good first issue"],
    },
    {
        "owner": "kestra-io",
        "repo": "kestra",
        "labels": ["good first issue"],
    },
    {
        "owner": "line",
        "repo": "armeria",
        "labels": ["good first issue"],
    },
    {
        "owner": "camunda",
        "repo": "camunda",
        "labels": ["good first issue"],
    },
    {
        "owner": "alibaba",
        "repo": "nacos",
        "labels": ["good first issue"],
    },
    {
        "owner": "alibaba",
        "repo": "Sentinel",
        "labels": ["good first issue"],
    },
    # ── Search / Databases ────────────────────────────────────────────────────
    {
        "owner": "elastic",
        "repo": "elasticsearch",
        "labels": ["good first issue"],
    },
    {
        "owner": "opensearch-project",
        "repo": "OpenSearch",
        "labels": ["good first issue"],
    },
    {
        "owner": "questdb",
        "repo": "questdb",
        "labels": ["Good first issue"],
    },
    {
        "owner": "dbeaver",
        "repo": "dbeaver",
        "labels": ["good first issue"],
    },
    {
        "owner": "apache",
        "repo": "doris",
        "labels": ["good first issue"],
    },
    {
        "owner": "apache",
        "repo": "shardingsphere",
        "labels": ["good first issue"],
    },
    {
        "owner": "crate",
        "repo": "crate",
        "labels": ["contributions welcome"],
    },
    {
        "owner": "hazelcast",
        "repo": "hazelcast",
        "labels": ["good first issue"],
    },
    {
        "owner": "vespa-engine",
        "repo": "vespa",
        "labels": ["good first issue"],
    },
    {
        "owner": "Graylog2",
        "repo": "graylog2-server",
        "labels": ["good first issue"],
    },
    # ── Observability / APM ───────────────────────────────────────────────────
    {
        "owner": "apache",
        "repo": "skywalking",
        "labels": ["good first issue"],
    },
    # ── Static Analysis / Code Quality ───────────────────────────────────────
    {
        "owner": "spotbugs",
        "repo": "spotbugs",
        "labels": ["good first issue"],
    },
    {
        "owner": "find-sec-bugs",
        "repo": "find-sec-bugs",
        "labels": ["good first issue"],
    },
    {
        "owner": "pmd",
        "repo": "pmd",
        "labels": ["good first issue"],
    },
    {
        "owner": "zaproxy",
        "repo": "zaproxy",
        "labels": ["good first issue"],
    },
    # ── Build Tools / Dev Tools ───────────────────────────────────────────────
    {
        "owner": "bazelbuild",
        "repo": "bazel",
        "labels": ["good first issue"],
    },
    {
        "owner": "GoogleContainerTools",
        "repo": "jib",
        "labels": ["good first issue"],
    },
    {
        "owner": "oracle",
        "repo": "opengrok",
        "labels": ["good first issue"],
    },
    {
        "owner": "typetools",
        "repo": "checker-framework",
        "labels": ["good first issue"],
    },
    # ── Collections / Libraries ───────────────────────────────────────────────
    {
        "owner": "eclipse",
        "repo": "eclipse-collections",
        "labels": ["good first issue"],
    },
    {
        "owner": "graphhopper",
        "repo": "graphhopper",
        "labels": ["good first issue"],
    },
    {
        "owner": "allure-framework",
        "repo": "allure2",
        "labels": ["good first issue"],
    },
    # ── JVM / Platform ────────────────────────────────────────────────────────
    {
        "owner": "eclipse",
        "repo": "openj9",
        "labels": ["good first issue"],
    },
    {
        "owner": "Sable",
        "repo": "soot",
        "labels": ["good first issue"],
    },
    # ── Data / Research Tools ─────────────────────────────────────────────────
    {
        "owner": "google",
        "repo": "data-transfer-project",
        "labels": ["good first issue"],
    },
    {
        "owner": "OpenRefine",
        "repo": "OpenRefine",
        "labels": ["Good First Issue"],
    },
    {
        "owner": "JabRef",
        "repo": "jabref",
        "labels": ["good first issue"],
    },
    # ── Android / Mobile ─────────────────────────────────────────────────────
    {
        "owner": "AntennaPod",
        "repo": "AntennaPod",
        "labels": ["Good first issue"],
    },
    {
        "owner": "TeamNewPipe",
        "repo": "NewPipe",
        "labels": ["good first issue"],
    },
    {
        "owner": "facebook",
        "repo": "fresco",
        "labels": ["good first issue"],
    },
    # ── Other ─────────────────────────────────────────────────────────────────
    {
        "owner": "bisq-network",
        "repo": "bisq",
        "labels": ["good first issue"],
    },
    {
        "owner": "MovingBlocks",
        "repo": "Terasology",
        "labels": ["Good First Issue"],
    },
    {
        "owner": "UniversalMediaServer",
        "repo": "UniversalMediaServer",
        "labels": ["good first issue"],
    },
    {
        "owner": "crossoverJie",
        "repo": "cim",
        "labels": ["good first issue"],
    },
    {
        "owner": "SasanLabs",
        "repo": "VulnerableApp",
        "labels": ["good first issue"],
    },
]


def fetch_issues(owner, repo, label, token=None):
    """Fetch open issues with a specific label from GitHub API."""
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/issues"
        f"?labels={label.replace(' ', '+')}&state=open&sort=created&direction=desc&per_page=20"
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

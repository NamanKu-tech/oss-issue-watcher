import csv
import io
import os
import json
import logging
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from urllib.parse import quote

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger("oss-watcher")


def gha_group(title):
    print(f"::group::{title}", flush=True)

def gha_endgroup():
    print("::endgroup::", flush=True)

def gha_error(msg):
    print(f"::error::{msg}", flush=True)

def gha_warning(msg):
    print(f"::warning::{msg}", flush=True)

def gha_notice(msg):
    print(f"::notice::{msg}", flush=True)

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

GEMINI_PROMPT = """You are an expert open source contributor advisor helping backend Java/SRE/Go/Rust developers find the best issues to contribute to.

For each GitHub issue below, provide ALL of these fields:
1. score (1-10): overall contribution worthiness
   - 10 = perfect: approachable, impactful, well-scoped, active repo, matches backend/SRE/systems skills
   - 1 = poor: too vague, stale, needs deep insider knowledge, or purely frontend
   Weigh: approachability (35%), skill match for backend/SRE/Go/Rust dev (30%), impact/visibility (20%), repo activity (15%)
2. what_to_do: 2-3 sentences — concrete code changes needed. Name specific files/functions/modules if you can infer them from the title and repo. What's the entry point?
3. time_estimate: realistic effort in plain English (e.g. "2-4 hours", "1-2 days", "3-5 days")
4. skill_tags: comma-separated list of specific skills needed (e.g. "Java, Spring MVC, JUnit", "Go, gRPC, protobuf", "Kubernetes, RBAC")

Return ONLY a valid CSV — no markdown fences, no explanation, no preamble.
Use this exact header row:
repo,issue_number,title,url,labels,created,score,what_to_do,time_estimate,skill_tags

Rules:
- Wrap any field containing commas in double-quotes
- Escape internal double-quotes by doubling them ("")
- One row per issue, same order as input
- score must be an integer 1-10
- Never leave what_to_do empty — if uncertain, give your best guess based on repo + labels

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


AI_BATCH_SIZE = 80

# Provider detection order: Vertex AI → Gemini AI Studio → OpenAI → Anthropic
# Set AI_MODEL secret to override the default model for whichever provider is active.
_PROVIDER_DEFAULTS = {
    "vertex":    "gemini-2.5-pro",     # GCP service account — uses billing credits
    "gemini":    "gemini-2.0-flash",   # AI Studio API key — free tier
    "openai":    "gpt-4o-mini",        # OpenAI API key — free trial or paid
    "anthropic": "claude-haiku-4-5-20251001",  # Anthropic API key — free trial or paid
}


def _detect_ai_provider():
    """Return (provider, auth, model) from available secrets, or (None, None, None)."""
    model_override = os.environ.get("AI_MODEL") or os.environ.get("GEMINI_MODEL") or ""

    sa_json = os.environ.get("GOOGLE_SA_JSON", "")
    if sa_json:
        model = model_override or _PROVIDER_DEFAULTS["vertex"]
        try:
            from google.oauth2 import service_account
            import google.auth.transport.requests as ga_requests
            sa_info = json.loads(sa_json)
            creds = service_account.Credentials.from_service_account_info(
                sa_info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            creds.refresh(ga_requests.Request())
            return "vertex", creds.token, model, sa_info.get("project_id")
        except Exception as e:
            gha_error(f"Vertex AI token failed: {e} — falling back to next provider")

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        model = model_override or _PROVIDER_DEFAULTS["gemini"]
        return "gemini", gemini_key, model, None

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        model = model_override or _PROVIDER_DEFAULTS["openai"]
        return "openai", openai_key, model, None

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        model = model_override or _PROVIDER_DEFAULTS["anthropic"]
        return "anthropic", anthropic_key, model, None

    return None, None, None, None


def _build_payload(provider, model, prompt):
    if provider in ("vertex", "gemini"):
        return json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 65536},
        }).encode()
    if provider == "openai":
        return json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 16384,
        }).encode()
    if provider == "anthropic":
        return json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 16384,
        }).encode()
    raise ValueError(f"Unknown provider: {provider}")


def _build_request(provider, auth, model, payload, project_id=None):
    headers = {"Content-Type": "application/json"}
    if provider == "vertex":
        url = (
            f"https://us-central1-aiplatform.googleapis.com/v1/projects/{project_id}/"
            f"locations/us-central1/publishers/google/models/{model}:generateContent"
        )
        headers["Authorization"] = f"Bearer {auth}"
    elif provider == "gemini":
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={auth}"
        )
    elif provider == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        headers["Authorization"] = f"Bearer {auth}"
    elif provider == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        headers["x-api-key"] = auth
        headers["anthropic-version"] = "2023-06-01"
    else:
        raise ValueError(f"Unknown provider: {provider}")
    return Request(url, data=payload, headers=headers)


def _extract_text(provider, result):
    if provider in ("vertex", "gemini"):
        return result["candidates"][0]["content"]["parts"][0]["text"]
    if provider == "openai":
        return result["choices"][0]["message"]["content"]
    if provider == "anthropic":
        return result["content"][0]["text"]
    raise ValueError(f"Unknown provider: {provider}")


def _call_ai(provider, auth, model, batch, project_id=None):
    """Single AI API call for one batch. Returns cleaned CSV text."""
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
    payload = _build_payload(provider, model, prompt)
    req = _build_request(provider, auth, model, payload, project_id=project_id)

    try:
        with urlopen(req) as resp:
            result = json.loads(resp.read().decode())
    except HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} from {provider} API: {body}") from e

    csv_text = _extract_text(provider, result).strip()
    if csv_text.startswith("```"):
        csv_text = "\n".join(
            line for line in csv_text.splitlines() if not line.startswith("```")
        ).strip()
    return csv_text


def analyze_with_ai(issues):
    """Send all new issues to the configured AI provider in batches. Returns CSV or None."""
    provider, auth, model, project_id = _detect_ai_provider()

    if provider is None:
        gha_warning(
            "No AI provider configured — set one of: GOOGLE_SA_JSON, GEMINI_API_KEY, "
            "OPENAI_API_KEY, or ANTHROPIC_API_KEY. Falling back to label-based scores."
        )
        return None

    log.info(f"AI provider: {provider} | model: {model}")

    batches = [issues[i:i + AI_BATCH_SIZE] for i in range(0, len(issues), AI_BATCH_SIZE)]
    gha_group(f"AI Analysis [{provider} / {model}] — {len(issues)} issues in {len(batches)} batch(es)")

    header = None
    all_rows = []
    failed = 0

    for idx, batch in enumerate(batches):
        try:
            log.info(f"Batch {idx + 1}/{len(batches)}: sending {len(batch)} issues...")
            csv_text = _call_ai(provider, auth, model, batch, project_id=project_id)
            lines = [l for l in csv_text.splitlines() if l.strip()]
            if not lines:
                gha_warning(f"Batch {idx + 1}: empty response")
                failed += 1
                continue
            rows_in_batch = len(lines) - 1
            if header is None:
                header = lines[0]
                all_rows.extend(lines[1:])
            else:
                data_lines = lines[1:] if lines[0] == header else lines
                all_rows.extend(data_lines)
            log.info(f"Batch {idx + 1}/{len(batches)}: OK — {rows_in_batch} rows scored")
        except Exception as e:
            failed += 1
            gha_error(f"Batch {idx + 1}/{len(batches)} FAILED: {e}")

    gha_endgroup()

    if header is None:
        gha_error("All AI batches failed — falling back to label-based scores only.")
        return None

    if failed:
        gha_warning(f"{failed}/{len(batches)} batches failed — those issues use label-based scores.")

    combined = "\n".join([header] + all_rows)
    gha_notice(f"AI scoring done: {len(all_rows)}/{len(issues)} issues scored ({failed} batch failures)")
    return combined


def parse_gemini_csv(csv_text):
    """Parse Gemini CSV into {url: {score, what_to_do, time_estimate, skill_tags}} dict."""
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
                "time_estimate": row.get("time_estimate", "").strip(),
                "skill_tags": row.get("skill_tags", "").strip(),
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
    writer.writerow(["repo", "issue_number", "title", "url", "labels", "areas", "created", "score", "what_to_do", "time_estimate", "skill_tags"])
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
            g.get("time_estimate") or "—",
            g.get("skill_tags") or "—",
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
        g = gemini_scores.get(issue["url"], {})
        score = g.get("score") or issue["difficulty"]
        score_color = "#28a745" if score >= 7 else "#e36209" if score >= 4 else "#586069"
        what_to_do = g.get("what_to_do", "")
        time_estimate = g.get("time_estimate", "")
        skill_tags = g.get("skill_tags", "")
        meta_parts = []
        if time_estimate:
            meta_parts.append(f"⏱ {time_estimate}")
        if skill_tags:
            meta_parts.append(f"🔧 {skill_tags}")
        meta_line = "  ·  ".join(meta_parts)
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
                {"<p style='color:#586069;font-size:11px;margin:4px 0 0;'>" + meta_line + "</p>" if meta_line else ""}
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

    log.info(f"Previously seen issues: {len(seen)}")
    log.info(f"Active repos: {len(active_repos)}/{len(WATCHED_REPOS)} (filtered to user areas)")
    skipped = [f"{r['owner']}/{r['repo']}" for r in WATCHED_REPOS if r not in active_repos]
    if skipped:
        log.info(f"Skipped repos (no user area match): {', '.join(skipped)}")

    gha_group(f"Scraping {len(active_repos)} repos")
    for config in active_repos:
        owner = config["owner"]
        repo = config["repo"]
        repo_key = f"{owner}/{repo}"
        for label in config["labels"]:
            issues = fetch_issues(owner, repo, label, token)
            new_count = 0
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
                    new_count += 1
            if new_count:
                log.info(f"{repo_key} [{label}]: {len(issues)} open, {new_count} new")
    gha_endgroup()

    gha_notice(f"Scraping complete — {len(new_issues)} new issues across {len(active_repos)} repos")

    if not new_issues:
        gha_notice("No new issues found. No emails sent.")
        save_seen_issues(seen)
        return

    raw_csv = analyze_with_ai(new_issues)
    gemini_scores = parse_gemini_csv(raw_csv) if raw_csv else {}
    log.info(f"AI scored {len(gemini_scores)}/{len(new_issues)} issues")

    gha_group("Sending emails")
    email_results = []
    for user in USER_CONFIGS:
        filtered = filter_issues_for_user(new_issues, user, gemini_scores)
        name = user.get("name", user["email"])
        diff_range = f"{user.get('difficulty_min',1)}-{user.get('difficulty_max',10)}"
        log.info(f"{name} <{user['email']}>: {len(filtered)} issues matched (difficulty {diff_range})")

        if not filtered:
            gha_warning(f"{name}: no issues matched filters — skipping email")
            email_results.append(f"  ⚠ {name} ({user['email']}): no matches")
            continue

        user_csv = build_user_csv(filtered, gemini_scores)
        html = build_email_html(filtered, gemini_scores, user_name=user.get("name"), total_found=len(new_issues))
        subject = f"🚀 {len(filtered)} OSS issue{'s' if len(filtered) > 1 else ''} matched for you!"
        ok = send_email(subject, html, recipient=user["email"], csv_attachment=user_csv)
        if ok:
            email_results.append(f"  ✓ {name} ({user['email']}): {len(filtered)} issues sent")
        else:
            email_results.append(f"  ✗ {name} ({user['email']}): email failed")
    gha_endgroup()

    gha_notice("Run summary:\n" + "\n".join(email_results))

    save_seen_issues(seen)
    log.info("Seen issues list saved.")


if __name__ == "__main__":
    main()

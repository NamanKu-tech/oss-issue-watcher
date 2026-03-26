# 🔔 OSS Issue Watcher

Get email notifications when new beginner-friendly issues are opened on open source projects you want to contribute to.

## Currently Watching

| Repo | Labels |
|------|--------|
| spring-projects/spring-boot | `status: first-timers-only`, `status: ideal-for-contribution` |
| spring-projects/spring-kafka | `status: ideal-for-contribution` |
| kafbat/kafka-ui | `good first issue` |
| testcontainers/testcontainers-java | `good first issue` |
| keycloak/keycloak | `good first issue` |
| debezium/debezium | `good first issue` |
| quarkusio/quarkus | `good first issue` |

## Setup (One-Time, ~10 Minutes)

### Step 1: Create Your Repo

1. Go to [github.com/new](https://github.com/new)
2. Name it `oss-issue-watcher`
3. Make it **Public** (GitHub Actions free minutes are unlimited for public repos)
4. Push the files from this project to the repo

### Step 2: Create a Gmail App Password

You need an App Password (NOT your regular Gmail password):

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. You may need to enable 2-Factor Authentication first
3. App name: `OSS Issue Watcher`
4. Click **Create**
5. Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)

### Step 3: Create a GitHub Personal Access Token

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Name: `oss-issue-watcher`
4. Expiration: 90 days (set a reminder to renew)
5. Scopes: check **`public_repo`** only
6. Click **Generate token**
7. Copy the token

### Step 4: Add Secrets to Your Repo

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these 4 secrets:

| Secret Name | Value |
|---|---|
| `GH_TOKEN` | Your GitHub personal access token from Step 3 |
| `SMTP_USERNAME` | Your Gmail address (e.g., `mukulghare9@gmail.com`) |
| `SMTP_PASSWORD` | The 16-char App Password from Step 2 |
| `NOTIFY_EMAIL` | Email where you want notifications (can be same as above) |

Optionally, if not using Gmail:

| Secret Name | Value |
|---|---|
| `SMTP_HOST` | SMTP server (default: `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP port (default: `587`) |

### Step 5: Test It

1. Go to your repo → **Actions** tab
2. Click **OSS Issue Watcher** on the left
3. Click **Run workflow** → **Run workflow**
4. Wait ~30 seconds, check your email

## How It Works

- GitHub Actions runs `check_issues.py` **every 2 hours**
- The script checks all watched repos via GitHub API for issues with the specified labels
- It tracks which issues it has already seen (in `seen_issues.json` via Actions cache)
- If new issues are found → sends you a formatted HTML email
- If no new issues → does nothing (no spam)

## Add More Repos

Edit `check_issues.py` and add to the `WATCHED_REPOS` list:

```python
{
    "owner": "apache",
    "repo": "kafka",
    "labels": ["newbie", "good first issue"],
},
```

## FAQ

**Q: Will I get spammed?**
No. You only get an email when NEW issues appear. Existing issues are tracked and skipped.

**Q: Is this free?**
Yes. GitHub Actions is free for public repos. Gmail SMTP is free.

**Q: The cron stopped running?**
GitHub disables Actions if no repo activity for 60 days. Just push a commit or manually trigger the workflow to re-enable.

**Q: How do I change the frequency?**
Edit the cron in `.github/workflows/watch-issues.yml`:
- Every hour: `'0 * * * *'`
- Every 2 hours: `'0 */2 * * *'` (default)
- Every 6 hours: `'0 */6 * * *'`

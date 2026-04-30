# Cron PR Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cache the AI-scored CSV to the repo after each watcher run so a Claude remote cron agent can read top issues and open draft PRs automatically — no connectors required.

**Architecture:** `check_issues.py` writes `latest_digest.csv` to disk after AI scoring. `watch-issues.yml` commits it back to the repo after each run. `seen_issues.json` is untouched. A Claude remote agent reads `latest_digest.csv`, picks the top 3 issues, and uses the GitHub REST API (via curl + PAT) to fork repos, create branches, attempt code changes, and open draft PRs.

**Tech Stack:** Python 3.12, GitHub Actions, GitHub REST API (curl), Claude.ai remote scheduled agents, pytest

---

## Tasks

### Task 1: Write `latest_digest.csv` after AI scoring

**Files:**

- Modify: `check_issues.py` — `main()` function
- Create: `tests/test_check_issues.py`

- [ ] **Step 1: Install pytest**

```bash
pip install pytest
```

- [ ] **Step 2: Write failing test**

Create `tests/test_check_issues.py`:

```python
import os
import sys
import unittest.mock as mock
import tempfile


def _import():
    """Import check_issues patching the module-level repos.json open."""
    with mock.patch("builtins.open", mock.mock_open(read_data="[]")):
        if "check_issues" in sys.modules:
            del sys.modules["check_issues"]
        import check_issues
    return check_issues


def test_latest_digest_csv_written_when_ai_returns_csv(tmp_path, monkeypatch):
    mod = _import()
    monkeypatch.chdir(tmp_path)

    dummy_csv = (
        "repo,issue_number,title,url,labels,areas,created,score,what_to_do,time_estimate,skill_tags\n"
        "apache/kafka,1,Fix bug,https://github.com/apache/kafka/issues/1,bug,,2026-04-30,8,Edit Foo.java,,Java\n"
    )

    monkeypatch.setattr(mod, "analyze_with_ai", lambda issues: dummy_csv)
    monkeypatch.setattr(mod, "USER_CONFIGS", [{"email": "x@x.com", "name": "X", "max_issues": 5, "difficulty_min": 1, "difficulty_max": 10, "areas": []}])
    monkeypatch.setattr(mod, "WATCHED_REPOS", [{"owner": "apache", "repo": "kafka", "labels": ["good first issue"], "areas": ["Java"]}])
    monkeypatch.setattr(mod, "fetch_issues", lambda *a, **kw: [{
        "id": 99999, "title": "Fix bug", "html_url": "https://github.com/apache/kafka/issues/1",
        "created_at": "2026-04-30T00:00:00Z", "number": 1, "labels": [{"name": "bug"}]
    }])
    monkeypatch.setattr(mod, "send_email", lambda *a, **kw: True)
    monkeypatch.setenv("SMTP_USERNAME", "x@x.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")

    mod.main()

    assert (tmp_path / "latest_digest.csv").exists()
    content = (tmp_path / "latest_digest.csv").read_text()
    assert "apache/kafka" in content
    assert "Fix bug" in content


def test_latest_digest_csv_not_written_when_ai_returns_none(tmp_path, monkeypatch):
    mod = _import()
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(mod, "analyze_with_ai", lambda issues: None)
    monkeypatch.setattr(mod, "USER_CONFIGS", [{"email": "x@x.com", "name": "X", "max_issues": 5, "difficulty_min": 1, "difficulty_max": 10, "areas": []}])
    monkeypatch.setattr(mod, "WATCHED_REPOS", [{"owner": "apache", "repo": "kafka", "labels": ["good first issue"], "areas": ["Java"]}])
    monkeypatch.setattr(mod, "fetch_issues", lambda *a, **kw: [{
        "id": 99999, "title": "Fix bug", "html_url": "https://github.com/apache/kafka/issues/1",
        "created_at": "2026-04-30T00:00:00Z", "number": 1, "labels": [{"name": "bug"}]
    }])
    monkeypatch.setattr(mod, "send_email", lambda *a, **kw: True)
    monkeypatch.setenv("SMTP_USERNAME", "x@x.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")

    mod.main()

    assert not (tmp_path / "latest_digest.csv").exists()
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd /Users/naman/work_applications/open_source_stuff/oss-issue-watcher
pytest tests/test_check_issues.py -v
```

Expected: `FAILED` — `latest_digest.csv` is never written yet.

- [ ] **Step 4: Add CSV write to `main()` in `check_issues.py`**

Find this block in `main()`:

```python
raw_csv = analyze_with_ai(new_issues)
gemini_scores = parse_gemini_csv(raw_csv) if raw_csv else {}
```

Add immediately after:

```python
if raw_csv:
    with open("latest_digest.csv", "w") as f:
        f.write(raw_csv)
    log.info("latest_digest.csv written (%d bytes)", len(raw_csv))
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
pytest tests/test_check_issues.py -v
```

Expected: both tests `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add check_issues.py tests/test_check_issues.py
git commit -m "feat: write latest_digest.csv after AI scoring for cron agent consumption"
```

---

### Task 2: Update `watch-issues.yml` to commit `latest_digest.csv` to repo

**Files:**

- Modify: `.github/workflows/watch-issues.yml`

- [ ] **Step 1: Add `contents: write` permission**

Find:

```yaml
jobs:
  check-issues:
    runs-on: ubuntu-latest
```

Add `permissions` block directly under `runs-on`:

```yaml
jobs:
  check-issues:
    runs-on: ubuntu-latest
    permissions:
      contents: write
```

- [ ] **Step 2: Add commit step after "Run issue checker"**

After the `run: python check_issues.py` step, insert:

```yaml
      - name: Commit digest artifacts
        if: always()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git pull --rebase origin main || true
          git add latest_digest.csv || true
          git diff --cached --quiet || git commit -m "chore: update digest artifacts [skip ci]"
          git push || true
```

- [ ] **Step 3: Verify YAML is valid**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/watch-issues.yml'))" && echo "YAML OK"
```

Expected: `YAML OK`. If `yaml` not installed: `pip install pyyaml` first.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/watch-issues.yml
git commit -m "ci: commit latest_digest.csv to repo after each watcher run"
```

---

### Task 3: Create initial state files for the cron agent

**Files:**

- Create: `fork_state.json`
- Create: `pr_attempted_urls.json`

- [ ] **Step 1: Create `fork_state.json`**

```bash
cat > fork_state.json << 'EOF'
{
  "daily": { "date": "", "count": 0 },
  "monthly": { "month": "", "count": 0 },
  "forked_repos": []
}
EOF
```

- [ ] **Step 2: Create `pr_attempted_urls.json`**

```bash
echo '[]' > pr_attempted_urls.json
```

- [ ] **Step 3: Confirm neither file is gitignored**

```bash
git check-ignore -v fork_state.json pr_attempted_urls.json
```

Expected: no output (neither is ignored).

- [ ] **Step 4: Commit**

```bash
git add fork_state.json pr_attempted_urls.json
git commit -m "chore: add initial cron agent state files"
```

---

### Task 4: Create the Claude remote cron routine

**Files:**

- No code files — performed on claude.ai/code/routines

- [ ] **Step 1: Create a GitHub Personal Access Token**

Go to [github.com/settings/tokens](https://github.com/settings/tokens) → Fine-grained tokens → Generate new token:

- Name: `oss-pr-pipeline`
- Repository access: **All repositories** (needs to fork any watched repo)
- Permissions: `Contents → Read and write`, `Pull requests → Read and write`, `Metadata → Read-only`

Copy the token — shown once only.

- [ ] **Step 2: Go to claude.ai/code/routines → New Routine**

| Field | Value |
| --- | --- |
| Name | `OSS Issue PR Pipeline` |
| Schedule | `0 8 * * *` |
| Model | `claude-sonnet-4-6` |
| Repo | `https://github.com/NamanKu-tech/oss-issue-watcher` |
| MCP Connections | none |

- [ ] **Step 3: Paste the following prompt (replace `GITHUB_PAT_HERE` with your token)**

```text
You are an automated OSS contribution agent for NamanKu-tech.

## SETUP
- GitHub username: NamanKu-tech
- GitHub PAT (keep private, never log it): GITHUB_PAT_HERE
- State repo cloned at: NamanKu-tech/oss-issue-watcher
- Fork limits: max 2 new forks/day, max 30/month

## STEP 1 — Read latest digest
Read latest_digest.csv from the cloned repo.
Columns: repo,issue_number,title,url,labels,areas,created,score,what_to_do,time_estimate,skill_tags

If missing or empty: exit with "No digest available — skipping run."

## STEP 2 — Read state
Read from cloned repo:
- fork_state.json
- pr_attempted_urls.json

Defaults if missing:
- fork_state.json: {"daily":{"date":"","count":0},"monthly":{"month":"","count":0},"forked_repos":[]}
- pr_attempted_urls.json: []

## STEP 3 — Select top 3 issues
1. Filter out rows whose url is already in pr_attempted_urls.json
2. Sort by score descending (non-numeric score = 0)
3. Take top 3

If 0 remain: exit with "All issues already attempted."

## STEP 4 — For EACH of the 3 issues:

### 4a — Fork check
Get today as YYYY-MM-DD, current month as YYYY-MM.
- If fork_state.daily.date != today: reset daily.count=0, daily.date=today
- If fork_state.monthly.month != current month: reset monthly.count=0, monthly.month=current month

Check fork exists (REPO_NAME = second part of repo field, e.g. "apache/kafka" → "kafka"):
curl -s -o /dev/null -w "%{http_code}" -H "Authorization: token GITHUB_PAT_HERE" https://api.github.com/repos/NamanKu-tech/{REPO_NAME}

200 → use existing fork, skip count increment.
404 → if daily.count>=2 OR monthly.count>=30: log "Fork limit — skipping" and move to next issue.
Otherwise fork:
curl -s -X POST -H "Authorization: token GITHUB_PAT_HERE" https://api.github.com/repos/{OWNER}/{REPO}/forks
Increment daily.count and monthly.count. Add "{owner}/{repo}" to forked_repos. Sleep 5s.

### 4b — Read CONTRIBUTING.md
curl -s -H "Authorization: token GITHUB_PAT_HERE" -H "Accept: application/vnd.github.raw" https://api.github.com/repos/{OWNER}/{REPO}/contents/CONTRIBUTING.md

If content contains "must be assigned", "request assignment", or "get assigned before": log "Assignment required — skipping" and move to next issue.

### 4c — Create branch
Branch name: fix/issue-{issue_number}-{slug}
{slug} = title lowercased, spaces→hyphens, only [a-z0-9-], max 40 chars.

Get default branch SHA:
curl -s -H "Authorization: token GITHUB_PAT_HERE" https://api.github.com/repos/NamanKu-tech/{REPO_NAME}/git/ref/heads/main
If 404, retry with heads/master.

Create branch:
curl -s -X POST -H "Authorization: token GITHUB_PAT_HERE" -H "Content-Type: application/json" \
  -d '{"ref":"refs/heads/{BRANCH_NAME}","sha":"{SHA}"}' \
  https://api.github.com/repos/NamanKu-tech/{REPO_NAME}/git/refs

### 4d — Attempt code changes
Use what_to_do field for file/function hints. For each file mentioned (max 5):

1. Read file from upstream:
curl -s -H "Authorization: token GITHUB_PAT_HERE" -H "Accept: application/vnd.github.raw" https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}

2. Make targeted code change based on the issue.

3. Get file SHA from fork branch:
curl -s -H "Authorization: token GITHUB_PAT_HERE" https://api.github.com/repos/NamanKu-tech/{REPO_NAME}/contents/{FILE_PATH}?ref={BRANCH_NAME}

4. Write changed file (base64-encode new content first):
curl -s -X PUT -H "Authorization: token GITHUB_PAT_HERE" -H "Content-Type: application/json" \
  -d '{"message":"fix: {short description}","content":"{BASE64}","sha":"{FILE_SHA}","branch":"{BRANCH_NAME}"}' \
  https://api.github.com/repos/NamanKu-tech/{REPO_NAME}/contents/{FILE_PATH}

If changes span >5 files or fix is unclear: skip code, open plan-only PR.

### 4e — Open draft PR
curl -s -X POST -H "Authorization: token GITHUB_PAT_HERE" -H "Content-Type: application/json" \
  -d '{"title":"fix: {ISSUE_TITLE} (#{ISSUE_NUMBER})","head":"NamanKu-tech:{BRANCH_NAME}","base":"main","body":"Closes #{ISSUE_NUMBER}\n\n## What changed\n{CHANGES_OR_PLAN}\n\n## Testing\n- [ ] Existing test suite passes\n- [ ] Unit tests added/updated\n- [ ] Follows CONTRIBUTING.md style guidelines\n\n---\n*Draft PR created by OSS Issue Watcher pipeline*","draft":true}' \
  https://api.github.com/repos/{OWNER}/{REPO}/pulls

Log the returned PR URL.

## STEP 5 — Commit state back to oss-issue-watcher
Update fork_state.json and pr_attempted_urls.json (append all 3 issue URLs, including skipped).
Commit both to NamanKu-tech/oss-issue-watcher main via GitHub Contents API:
1. GET current SHA of each file
2. PUT updated content

## STEP 6 — Print summary
=== OSS PR Pipeline Run ===
PRs opened: <URLs>
Skipped: <url> — <reason>
State updated: fork_state.json, pr_attempted_urls.json
```

- [ ] **Step 4: Save the routine and note the routine ID**

- [ ] **Step 5: Click Run Now and verify**

Check:

- Run log on [claude.ai/code/routines](https://claude.ai/code/routines) shows all 6 steps executed
- At least one draft PR appears on GitHub under a fork owned by NamanKu-tech
- `fork_state.json` and `pr_attempted_urls.json` updated in oss-issue-watcher repo

---

## Self-Review

**Spec coverage:**

- [x] `latest_digest.csv` written after scoring → Task 1
- [x] GitHub Actions commits `latest_digest.csv` → Task 2
- [x] Initial state files → Task 3
- [x] Claude cron routine with full curl-based prompt → Task 4
- [x] Fork rate limits (2/day, 30/month) → Task 4 prompt §4a
- [x] CONTRIBUTING.md assignment gate → Task 4 prompt §4b
- [x] Branch naming `fix/issue-{number}-{slug}` → Task 4 prompt §4c
- [x] Draft PR format with Closes #N → Task 4 prompt §4e
- [x] `pr_attempted_urls.json` deduplication → Task 4 prompt §3 + §5
- [x] `seen_issues.json` untouched by agent → agent never reads or writes it
- [x] No MCP connectors required → confirmed in Task 4 setup

**No placeholders.**

**Type consistency:** `latest_digest.csv` referenced consistently across Tasks 1, 2, and 4 prompt.

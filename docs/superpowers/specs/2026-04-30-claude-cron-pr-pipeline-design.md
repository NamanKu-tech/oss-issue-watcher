# Claude Cron PR Pipeline — Design Spec
**Date:** 2026-04-30

## Overview

A single Claude remote scheduled agent (daily cron, laptop-off capable) that reads `latest_digest.csv` directly from the oss-issue-watcher repo, picks the top 3 issues, and attempts to create a draft PR on a forked repo for each — using the GitHub REST API via curl with a Personal Access Token. No MCP connectors required.

---

## Architecture

```
[GitHub Actions — existing watch-issues.yml]
    │
    ├─► Scores issues with AI → builds latest_digest.csv
    └─► Commits latest_digest.csv to oss-issue-watcher repo

Claude Remote Agent (daily cron, 08:00 UTC)
    │
    ├─► Read latest_digest.csv from cloned oss-issue-watcher repo
    ├─► Read pr_attempted_urls.json + fork_state.json from repo
    ├─► Pick top 3 issues by score (exclude already-attempted URLs)
    │
    └─► For each of the 3 issues:
            ├─ Check/create fork via GitHub API (rate-limited)
            ├─ Create branch: fix/issue-{number}-{slug}
            ├─ Read CONTRIBUTING.md from upstream repo
            ├─ Read relevant source files (guided by what_to_do from CSV)
            ├─ Attempt code changes via GitHub Contents API
            ├─ Open draft PR on upstream from fork
            └─ Update fork_state.json + pr_attempted_urls.json → commit back
```

---

## Code Changes Required

### 1. `check_issues.py`

**`seen_issues.json` — add timestamps**

Current format (integer IDs only):
```json
["123456789", "987654321"]
```

New format (ID → ISO timestamp):
```json
{
  "123456789": "2026-04-30T08:00:00Z",
  "987654321": "2026-04-29T12:00:00Z"
}
```

Update `load_seen_issues` and `save_seen_issues` to handle dict instead of set.
Store `datetime.now(timezone.utc).isoformat()` as the value when adding a new issue ID.

**Write `latest_digest.csv`**

After `analyze_with_ai` returns `raw_csv`, write it to disk:
```python
if raw_csv:
    with open("latest_digest.csv", "w") as f:
        f.write(raw_csv)
```

This is the full AI-scored CSV (all users, all repos) — not filtered per user.

### 2. `watch-issues.yml`

Add a commit step after the existing "Run issue checker" step:
```yaml
- name: Commit digest CSV and seen issues
  run: |
    git config user.name "github-actions[bot]"
    git config user.email "github-actions[bot]@users.noreply.github.com"
    git add latest_digest.csv seen_issues.json
    git diff --cached --quiet || git commit -m "chore: update digest and seen issues [skip ci]"
    git push
```

Add `contents: write` permission to the job.

---

## Agent Components

### 1. Trigger
- Platform: Claude.ai remote scheduled agent
- Schedule: `0 8 * * *` (daily 08:00 UTC = 09:00 Dublin)
- Repo cloned: `https://github.com/NamanKu-tech/oss-issue-watcher`
- Connectors: none
- GitHub access: Personal Access Token (PAT) with `repo` scope, stored in routine prompt

### 2. Issue Selection
- Read `latest_digest.csv` from cloned repo
- Filter out URLs already in `pr_attempted_urls.json`
- Sort by `score` descending → take top 3
- If fewer than 3 remain, work with however many there are

### 3. Fork Management
Rate limits via `fork_state.json` in oss-issue-watcher repo:

```json
{
  "daily": { "date": "2026-04-30", "count": 1 },
  "monthly": { "month": "2026-04", "count": 3 },
  "forked_repos": ["apache/kafka", "grafana/grafana"]
}
```

Logic per issue:
- `forked_repos` contains `{owner}/{repo}` → use existing fork, no count increment
- `daily.count >= 2` or `monthly.count >= 30` → skip issue (log reason)
- Otherwise → fork via `POST /repos/{owner}/{repo}/forks`, increment counters

Date/month resets: if `daily.date` ≠ today reset count to 0; if `monthly.month` ≠ current month reset count to 0.

### 4. Branch + Code + PR

**Branch naming:**
```
fix/issue-{issue_number}-{slug}
```
`{slug}` = title lowercased, spaces → hyphens, max 40 chars, no special characters.

**GitHub API calls (all via curl + PAT):**
```
POST /repos/{owner}/{repo}/forks                    ← fork
POST /repos/NamanKu-tech/{repo}/git/refs            ← create branch
GET  /repos/{owner}/{repo}/contents/CONTRIBUTING.md ← check assignment rules
GET  /repos/{owner}/{repo}/contents/{path}          ← read source files
PUT  /repos/NamanKu-tech/{repo}/contents/{path}     ← write code changes
POST /repos/{owner}/{repo}/pulls                    ← open draft PR
```

**CONTRIBUTING.md gate:** if it explicitly requires maintainer assignment before PR → skip issue.

**Complexity gate:** if changes span >5 files → open PR with plan-only body, no code commits.

**Draft PR format:**
```
Title: fix: {issue title} (#{issue_number})

Closes #{issue_number}

## What changed
{changes made, or plan if too complex}

## Testing
- [ ] Existing test suite passes
- [ ] Unit tests added/updated
- [ ] Follows CONTRIBUTING.md style guidelines

---
*Draft PR created by OSS Issue Watcher pipeline*
```

### 5. State Updates
Agent commits back to oss-issue-watcher repo after processing all 3 issues:
- `fork_state.json` — updated counts + forked_repos
- `pr_attempted_urls.json` — all 3 URLs appended (including skipped, to avoid retrying)

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| `latest_digest.csv` missing from repo | Agent exits, logs "no digest available" |
| CSV has 0 unprocessed issues | Agent exits cleanly |
| CONTRIBUTING.md requires assignment | Skip issue, move to next |
| Fork limit hit | Skip issues needing new forks, attempt already-forked repos |
| Code change too complex (>5 files) | Open plan-only draft PR |
| GitHub API error | Log error, skip to next issue |

---

## Constraints

- `seen_issues.json` is owned by `watch-issues.yml` — agent never reads or writes it
- Agent fork account: `NamanKu-tech`
- GitHub PAT stored in routine prompt (private to user's Claude.ai account)
- All GitHub operations use REST API via curl — no git clone of target repos needed
- CONTRIBUTING.md always read before any code change attempt

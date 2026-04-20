# How to Claim an Open Source Issue

## 1. Find an issue worth picking up

Check the email digest — every issue has a **score (1–10)** and a **what_to_do** summary in the attached CSV. Sort by score descending and pick something in the 6–9 range: high enough to matter, not so hard you get stuck.

## 2. Do your homework first

Before commenting:
- Read the issue thread fully — someone may have already started work
- Check open PRs for the repo (`is:pr is:open`) — search the issue number to see if a fix is in progress
- Skim `CONTRIBUTING.md` — some repos require you to be assigned before submitting a PR

## 3. Claim it with a comment

Post a short comment on the issue:

```
Hi, I'd like to work on this. I'll have a draft PR up within [X days].
```

Keep it brief. Don't ask for permission to start — just say you're on it and give a timeline. Maintainers notice when contributors disappear after claiming, so only commit to a timeline you can keep.

## 4. Fork → branch → fix

```bash
# Fork on GitHub, then:
git clone https://github.com/YOUR_USERNAME/REPO.git
cd REPO
git checkout -b fix/issue-1234-short-description
```

Use the issue number in the branch name — it makes the PR easy to trace.

## 5. Open a draft PR early

Push your branch and open a **Draft PR** as soon as you have something, even if incomplete:

```
gh pr create --draft --title "fix: [short description] (#1234)" \
  --body "Closes #1234

## What changed
- ...

## Testing
- [ ] Unit tests added/updated
- [ ] Ran existing test suite locally"
```

Draft PRs signal you're actively working and prevent others from duplicating effort.

## 6. Mark ready when done

Convert from Draft → Ready for Review only when:
- All tests pass locally
- You've addressed linting/style requirements from `CONTRIBUTING.md`
- The PR description clearly links the issue (`Closes #1234`)

## 7. Follow up

- Respond to review comments within 48 hours — slow responses are the #1 reason good PRs get abandoned
- If a maintainer requests changes, push a new commit (don't force-push unless asked)
- If you're blocked or need to drop the issue, say so in a comment so someone else can pick it up

## Tips

- **Speed matters** on popular repos — comment and open a draft PR the same day
- **Small focused PRs** merge faster than large ones; if the fix touches unrelated code, split it
- **Tests are non-negotiable** for most mature projects — check existing test patterns before writing your own
- If a repo uses `gh issues assign @me`, do that instead of a comment

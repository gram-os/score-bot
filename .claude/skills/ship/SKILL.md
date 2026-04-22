---
name: ship
description: Run checks, commit all changes, and open a pull request with an auto-generated description. Use prior to committing changes to a branch.
---

Ship the current branch: run `make check`, commit any uncommitted changes, then open a pull request.

## Steps

1. **Get branch context**
   - Run `git branch --show-current` to get the current branch name.
   - If on `main`, stop and tell the user that a new branch will be created. Create a new branch with the following format: {type (fix, feat, docs, etc.)}/{three-word-description(checkout-session-create)}. (e.g. feat/checkout-session-create, fix/update-title-parsing)

2. **Run checks**
   - Run `make check` (black + flake8 + pytest).
   - If it fails, stop and show the output. Do not commit or open a PR.
   - Attempt to remedy the issue by applying the necessary formatting. If there are failing tests, attempt to resolve the issue

3. **Stage and commit**
   - Run `git status` to see what's unstaged or untracked.
   - If there are changes, stage specific files (avoid `git add -A`; skip `.env`, secrets, and large binaries).
   - Run `git diff --cached` and `git log --oneline -10` to understand what's being committed.
   - Write a concise commit message (imperative mood, one sentence) that describes the *why*, not the *what*.
   - Commit using a HEREDOC so formatting is preserved.
   - If there is nothing to commit (clean working tree), skip this step and proceed to PR creation.

4. **Push**
   - Push the branch to origin with `git push -u origin <branch>` if it has no upstream yet, otherwise `git push`.

5. **Open a pull request**
   - Run `git log main..HEAD --oneline` and `git diff main...HEAD` to understand the full set of changes vs main.
   - Draft a PR title (≤70 chars, imperative) and a body with:
     - A short summary (2-4 bullet points of what changed and why)
     - A test plan checklist
     - `🤖 Generated with [Claude Code](https://claude.com/claude-code)`
   - Create the PR with `gh pr create`.
   - Return the PR URL to the user.

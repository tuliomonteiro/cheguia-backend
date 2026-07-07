---
name: ship
description: Branch, commit, and open a PR the way this repo does it — always from the true remote tip, with this repo's naming and commit style, and with main kept in sync after merges. Use when starting a new piece of work or when work is done and ready for review.
---

# Ship

This repo's history has one recurring failure: stacked feature branches merged into each
other while `main` stayed months behind (`main` once held only PR #1 while the real code
lived on `docs/readme`, 6 commits ahead). Everything below exists to prevent a repeat.

## Mode A — Starting work

### 1. Find the true tip (never trust local `main`)

```bash
git fetch --all --prune
git log --oneline --graph --decorate --all | head -30
# The branch containing the newest real work:
for b in $(git branch -r | grep -v HEAD); do echo "$(git log -1 --format='%ci' $b) $b"; done | sort -r | head -5
```

Decide the base:
- If `origin/main` contains all remote branches' work → base on `origin/main`. ✅ normal case
- If some `origin/<branch>` is ahead of `origin/main` (check with
  `git log --oneline origin/main..origin/<branch>`) → **stop and tell the user**: "main
  is N commits behind <branch>; I'll base on <branch>, and we should merge <branch> into
  main first / alongside." Base on the tip, not on stale main. Do not silently re-stack.

### 2. Branch

Naming, from this repo's history: `feat/<kebab-topic>`, `fix/<kebab-topic>`,
`docs/<kebab-topic>`.

```bash
git checkout -b feat/rate-limiting origin/main   # or the true tip from step 1
```

### 3. Also check for uncommitted strays

`git status` before starting. If the working tree already has unrelated modifications,
ask whether they're wanted before mixing them into your branch.

## Mode B — Work is done, ship it

### 1. Pre-flight (all must pass — these mirror CLAUDE.md §5 "Branch/PR")

```bash
git status --porcelain            # review every file; no .env, venv/, __pycache__, stray PDFs/test files
python manage.py check
python manage.py makemigrations --check --dry-run   # no forgotten migrations
python manage.py test             # must pass; "no tests ran" is a warning, not a pass
grep -rn "sk-[a-zA-Z0-9]" --include='*.py' . | grep -v example && echo "LEAKED KEY?" || true
```

Also confirm docs moved with the code: if you added a setting/env var/endpoint/command,
`.env.example` and README changed in this diff too (`git diff --stat`).

### 2. Commit

Style from history — imperative, capitalized, no trailing period, ≤ 72 chars, body
explains *why* when non-obvious:

```
Add rate limiting to chat endpoints

Anonymous quick-chat was an open relay to the OpenAI key in dev
deployments. Throttle per-IP for anon, per-user for authenticated.
```

One logical change per commit. Don't bundle a refactor with a feature. End with:
`Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

### 3. Push and open the PR

```bash
git push -u origin feat/rate-limiting
gh pr create --base main --title "Add rate limiting to chat endpoints" --body "$(cat <<'EOF'
## What
- <bullet the changes>

## Why
<one paragraph>

## Verification
- <what you actually ran and its result — mirror CLAUDE.md §5 checklists>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

`--base main` unless the work deliberately stacks on an open PR — in that case
`--base <that-branch>` AND note in the PR body: "Stacked on #N — merge that first,
then retarget or merge this." Stacking is allowed; *forgetting the stack* is the bug.

**Never merge the PR yourself** (CLAUDE.md §6). Report the PR URL and stop.

## Mode C — After the user merges (run when asked to "sync" or before new work)

```bash
git fetch --all --prune
git checkout main && git merge --ff-only origin/main
# Verify nothing is still ahead of main:
for b in $(git branch -r | grep -v HEAD | grep -v origin/main); do
  n=$(git log --oneline origin/main..$b | wc -l | tr -d ' '); [ "$n" != "0" ] && echo "$b is $n ahead of main";
done
```

If a branch is still ahead: it's either an open PR (fine — say so) or a merged-but-
drifted stack (the historical failure) — tell the user which branches contain unmerged
work and propose the order to land them. Delete fully-merged local branches
(`git branch --merged main`), but never delete remote branches without being asked.

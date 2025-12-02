# Git Workflow - CRITICAL RULES

## ⚠️ PROTECTED BRANCHES - ABSOLUTE REQUIREMENT ⚠️

**NEVER COMMIT DIRECTLY TO `main` OR `develop` BRANCHES!**

These branches are PROTECTED and require Pull Requests for all changes.

### MANDATORY Workflow for Every Task:

1. **ALWAYS** create a feature branch from `develop` before starting work
2. **ALWAYS** work on the feature branch
3. **ALWAYS** commit to the feature branch
4. **ALWAYS** open a Pull Request to merge into `develop`
5. **NEVER** commit directly to `develop` or `main`

## Branch Naming Convention

- Feature branches: `feature/<task-name-kebab-case>`
- Example: `feature/cookie-management-system`
- Use only ASCII characters, no spaces, no emoji

## Step-by-Step Process for Each Task

### Before Starting Any Task:

```bash
# 1. Ensure you're on develop and it's up to date
git checkout develop
git pull origin develop

# 2. Create a new feature branch with upstream tracking
git checkout -b feature/<task-name>

# 3. Set up upstream tracking for the new branch
git push -u origin feature/<task-name>

# 4. Verify you're on the feature branch with tracking
git branch --show-current  # Should show feature/<task-name>
git branch -vv  # Should show [origin/feature/<task-name>]
```

**CRITICAL:** Always create branches with upstream tracking to prevent "no tracking information" errors.

### During Task Implementation:

```bash
# Commit frequently to the feature branch
git add <files>
git commit -m "type: description"

# Push to remote feature branch (tracking already set up)
git push

# If tracking is not set up, use:
git push -u origin feature/<task-name>

# Verify tracking status anytime with:
git branch -vv
```

### After Task Completion:

```bash
# 1. Push final changes (tracking already set)
git push

# 2. Open Pull Request on GitHub/GitLab
#    - Source: feature/<task-name>
#    - Target: develop
#    - Use merge commit (NOT squash or rebase)

# 3. After PR is merged, delete the feature branch
git checkout develop
git pull origin develop
git branch -d feature/<task-name>
git push origin --delete feature/<task-name>  # Delete remote branch
```

## Commit Message Format (Conventional Commits)

- **Format:** `type[optional-scope]: short subject`
- **Types:** feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert
- **Subject:** Imperative form, ~72 chars max, no period, no emoji
- **Body (optional):** Explain what and why
- **Footer (optional):** Reference tickets (e.g., `Refs TICKET-123`)

### Examples:

```
feat: add cookie validation service
fix: handle null values in video metadata
refactor: extract retry logic to utility function
test: add unit tests for provider manager
docs: update README with cookie setup instructions
chore: wip - partial implementation of rate limiter
```

## Safety Rules

### ❌ FORBIDDEN Actions:

- Committing directly to `develop` or `main`
- Force pushing (`git push --force`)
- Rewriting history (`git rebase`, `git commit --amend` on pushed commits)
- Squashing commits in PRs (use merge commits)

### ✅ REQUIRED Actions:

- Always work on feature branches
- Always open PRs for merging to `develop`
- Preserve commit history (no rebase/squash)
- Push commits regularly
- Delete feature branch after PR merge

## Branch Tracking Verification

Always ensure your feature branch has upstream tracking configured:

```bash
# Check tracking status
git branch -vv

# If tracking is missing, set it up:
git branch --set-upstream-to=origin/feature/<task-name>

# Or push with -u flag:
git push -u origin feature/<task-name>
```

**Common Error:** "There is no tracking information for the current branch"
**Solution:** Always use `git push -u origin <branch-name>` on first push

## Emergency Recovery

If you accidentally committed to `develop`:

```bash
# 1. Create a feature branch with the changes
git checkout -b feature/<task-name>
git push -u origin feature/<task-name>  # Set up tracking

# 2. Reset develop to remote state
git checkout develop
git reset --hard origin/develop

# 3. Continue working on the feature branch
git checkout feature/<task-name>
```

## Pre-Push Checklist

Before every push, verify:

- [ ] I am NOT on `develop` or `main` branch
- [ ] I am on a `feature/*` branch
- [ ] Branch has upstream tracking configured (`git branch -vv`)
- [ ] Commit messages follow conventional commits format
- [ ] All tests pass (if applicable)
- [ ] Code is formatted and linted

## Quick Reference: Git Commands

### Creating a New Feature Branch

```bash
# From develop
git checkout develop
git pull origin develop
git checkout -b feature/<task-name>
git push -u origin feature/<task-name>  # CRITICAL: Set up tracking
```

### Working on Existing Feature Branch

```bash
# Switch to branch
git checkout feature/<task-name>

# Verify tracking
git branch -vv

# If no tracking, set it up
git push -u origin feature/<task-name>

# Regular commits and pushes
git add .
git commit -m "feat: description"
git push  # Works because tracking is set
```

### Checking Branch Status

```bash
# Show current branch
git branch --show-current

# Show all branches with tracking info
git branch -vv

# Show remote branches
git branch -r
```

## Enforcement

This workflow is MANDATORY for all development work. No exceptions.

**Remember: Protected branches = Feature branches + Pull Requests ALWAYS!**

**Key Rule:** Always use `git push -u origin <branch-name>` on the first push to set up tracking.

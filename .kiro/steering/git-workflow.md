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

# 2. Create a new feature branch
git checkout -b feature/<task-name>

# 3. Verify you're on the feature branch
git branch --show-current  # Should show feature/<task-name>
```

### During Task Implementation:

```bash
# Commit frequently to the feature branch
git add <files>
git commit -m "type: description"

# Push to remote feature branch
git push origin feature/<task-name>
```

### After Task Completion:

```bash
# 1. Push final changes
git push origin feature/<task-name>

# 2. Open Pull Request on GitHub/GitLab
#    - Source: feature/<task-name>
#    - Target: develop
#    - Use merge commit (NOT squash or rebase)

# 3. After PR is merged, delete the feature branch
git checkout develop
git pull origin develop
git branch -d feature/<task-name>
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

## Emergency Recovery

If you accidentally committed to `develop`:

```bash
# 1. Create a feature branch with the changes
git checkout -b feature/<task-name>

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
- [ ] Commit messages follow conventional commits format
- [ ] All tests pass (if applicable)
- [ ] Code is formatted and linted

## Enforcement

This workflow is MANDATORY for all development work. No exceptions.

**Remember: Protected branches = Feature branches + Pull Requests ALWAYS!**

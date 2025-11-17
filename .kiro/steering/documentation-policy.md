# Documentation Policy

## Critical Rule: Minimize Documentation Files

**Think twice before creating new documentation files.**

### When NOT to Create Documentation

❌ **Never create documentation for:**
- One-time fixes or bug resolutions
- Test results or CI/CD troubleshooting
- Temporary workarounds
- Activity summaries or work logs
- Implementation details that will change
- Information that duplicates commit messages
- Step-by-step guides for completed tasks

### When to Create Documentation

✅ **Only create documentation for:**
- **Setup guides** that users will repeatedly reference (e.g., DEVELOPMENT_SETUP.md)
- **Architecture decisions** that affect long-term design
- **API contracts** that external consumers depend on
- **Configuration references** for complex systems
- **Troubleshooting guides** for recurring issues (not one-time fixes)

### Documentation Maintenance

- **Prefer existing files**: Add to README.md or existing docs rather than creating new files
- **Avoid duplication**: Don't document what's already in code comments or commit messages
- **Keep it current**: Outdated docs are worse than no docs
- **Delete obsolete docs**: Remove files when they're no longer relevant

### Examples

**Bad (don't create):**
- `CI_MYPY_FIX.md` - One-time CI fix (use commit message instead)
- `TESTING_RESULTS.md` - Test output (ephemeral data)
- `BUGFIX_SUMMARY.md` - Bug fix details (use commit message)
- `IMPLEMENTATION_LOG.md` - Work diary (not needed)

**Good (acceptable):**
- `DEVELOPMENT_SETUP.md` - Developers reference this repeatedly
- `API.md` - External contract that must be stable
- `ARCHITECTURE.md` - Long-term design decisions
- `CONTRIBUTING.md` - Process that doesn't change often

### Integration Over Creation

Before creating a new file, ask:
1. Can this go in README.md?
2. Can this be added to an existing doc?
3. Will this be referenced more than once?
4. Will this still be relevant in 6 months?

If the answer to #3 or #4 is "no", **don't create the file**.

### Commit Messages Are Documentation

Good commit messages eliminate the need for many docs:
- Explain the "why" in commit messages
- Reference issues/tickets for context
- Use conventional commits for categorization
- Detailed commit bodies are better than separate docs

## Enforcement

When asked to create documentation:
1. Challenge the need for a new file
2. Suggest alternatives (README, existing docs, commit messages)
3. Only create if it meets the "acceptable" criteria above
4. Keep it minimal and maintainable

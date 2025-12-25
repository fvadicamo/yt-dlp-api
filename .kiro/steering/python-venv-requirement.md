---
inclusion: always
---

# Python Virtual Environment Requirement

## Critical Rule: Always Use Virtual Environments

**NEVER use system/global Python for development tasks.**

Before running ANY Python or pip command, you MUST:

1. Check if a virtual environment exists
2. If not, create one using `python3 -m venv venv` or `python -m venv venv`
3. Activate it:
   - macOS/Linux: `source venv/bin/activate`
   - Windows: `venv\Scripts\activate`
4. Verify activation by checking `which python` or `python --version`
5. Only then proceed with pip installs or Python execution

## Commands to Always Use

```bash
# Create virtual environment (if not exists)
python3 -m venv venv

# Activate (macOS/Linux)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Verify
which python  # Should show venv/bin/python
pip list      # Should show minimal packages

# Then install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Why This Matters

- Prevents polluting system Python
- Ensures reproducible environments
- Avoids permission issues
- Isolates project dependencies
- Standard best practice for Python development

## Enforcement

This rule applies to ALL Python projects in ALL workspaces. No exceptions.

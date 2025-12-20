# Code Review Instructions

You are reviewing Pull Request #{{ PR_NUMBER }} for {{ REPOSITORY }}.

## Task

Review ONLY the changes introduced by this PR. Analyze the diff between:
- Base: {{ BASE_SHA }}
- Head: {{ HEAD_SHA }}

## Review Focus

1. **Security vulnerabilities**
   - Command injection, path traversal, SQL injection
   - Improper input validation
   - Secrets or credentials in code

2. **Async/await correctness**
   - Missing await on async calls
   - Race conditions
   - Proper error handling in async context

3. **Type hints and correctness**
   - Missing or incorrect type annotations
   - Type mismatches

4. **Error handling**
   - Uncaught exceptions
   - Missing error cases
   - Improper error messages

5. **Code quality**
   - Logic errors
   - Performance issues
   - Code duplication

## Output Requirements

For each finding:
- Provide EXACT file path relative to repository root
- Provide EXACT line numbers where the issue occurs
- Assign priority: 0=critical, 1=high, 2=medium, 3=low
- Be concise but specific in the explanation
- Suggest a fix when possible

**CRITICAL**: Ensure file paths and line numbers are exactly correct.
Incorrect locations will cause comments to be rejected.

## PR Context

Title: {{ PR_TITLE }}

Description:
{{ PR_BODY }}

Changed files:
{{ CHANGED_FILES }}

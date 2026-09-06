# Context

- [_docs/plan.md](_docs/plan.md) defines approved product behavior.
- [GitHub Issues](https://github.com/TingyiWei2024/household-chores-ai-dev/issues)
  are the only active execution queue. [backlog.md](backlog.md) preserves the
  homework/planning snapshot and real task-to-issue index.
- Escalate genuine product conflicts or missing decisions instead of guessing.

# Documents

- Read [_docs/process.md](_docs/process.md) before starting work. The main session
  orchestrates separate native subagents; it does not perform their roles itself.
- Roles: [PM](_docs/team/pm.md), [Engineer](_docs/team/software-engineer.md),
  [QA](_docs/team/qa-engineer.md).
- Groom issues with [_docs/task-template.md](_docs/task-template.md).

# Rules

- Do not modify `_docs/plan.md` or `backlog.md` unless explicitly asked.
- Stay within the approved MVP and selected issue; preserve unrelated changes.
- Do not add dependencies without explicit authorization.
- Engineer local commits are authorized only for dispatched implementation on
  the designated non-main branch; follow the Git boundaries in `process.md`.
- Issue writes and integration actions require the authorization in `process.md`.

# Commands

- Install dependencies: `uv sync`
- Run migrations: `uv run python manage.py migrate`
- Run development server: `uv run python manage.py runserver`
- Run tests: `uv run python manage.py test`

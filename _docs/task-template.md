## Goal

Describe the intended outcome in one or two sentences.

## Acceptance criteria

- [ ] State one observable result per criterion, including relevant edge cases.
- [ ] Specify acting role, action, expected behavior, and persisted-data effects
      where permissions or rejected requests matter.

## Out of scope

- State explicit exclusions from this issue.
- Link required work belonging elsewhere to its existing issue. If no issue
  exists, record a proposed follow-up and its unresolved tracking status; create
  and link it only with authorization. Never silently omit required work.

## Constraints

- Link the approved product specification and relevant implementation guidance.
- Identify the allowed files/areas, existing mechanisms to reuse, and dependencies
  on other tasks/issues, including whether their integration is confirmed.
- Specify library restrictions and the designated non-main working branch.
- Use Django's built-in runner: `uv run python manage.py test`; add no dependencies.
- Follow [process.md](process.md) for role handoffs, local commits, issue writes,
  and the human integration decision.

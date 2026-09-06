# Development Process

This workflow follows the task template, role contracts, and orchestrator loop in
[AI-Native Development: Specifications, Loop and Graph Engineering](https://aishippingblog.com/p/ai-native-development-specifications),
with the project adaptations below. It uses one working tree and one issue at a
time. The mature Retroloop repository's parallel-worktree process is not used.

## Sources and task tracking

- Read [../AGENTS.md](../AGENTS.md), [plan.md](plan.md), the current task source,
  and the assigned role document before working. Read the selected task's goal,
  acceptance criteria, exclusions, constraints, and dependencies at each handoff.
- `plan.md` is the frozen product specification. Preserve its behavior; do not
  modify it or [../backlog.md](../backlog.md) without explicit user authorization.
- Tasks 1–3 are accepted. Tasks 4–8 have been migrated to GitHub Issues, which are
  now the only active execution queue. Resolve their real issue links from the
  [task-to-issue index](../backlog.md#task-to-issue-index).
- `backlog.md` retains the original goal, criteria, exclusions, and dependencies
  as the homework/planning snapshot. Do not maintain competing execution status
  or groomed acceptance criteria there; update the mapped issue when authorized.
- Issue creation, edits, comments, and closure require authorization for the
  migration or workflow. Carry that authorization through handoffs; do not ask
  again for covered operations. Never invent issue numbers or successful writes.
- If issue access or authorized writes are unavailable, report the exact blocker.
  A chat draft does not satisfy PM's requirement to update the issue. Do not
  substitute an unauthorized backlog edit or start an issue-based pilot before
  its migration is complete.

## Roles and dispatch

The main session is the orchestrator. After setup, it selects permitted work,
dispatches agents, carries evidence between them, and reports progress. It does
not groom issues, implement application code, or perform QA itself.

- [PM](team/pm.md) updates one issue using [task-template.md](task-template.md).
- [Engineer](team/software-engineer.md) implements and locally commits that issue.
- [QA](team/qa-engineer.md) independently verifies the Engineer's finished revision.

Use actual separate native subagents with explicit Markdown role instructions.
In sessions exposing the `collaboration` tools, use `spawn_agent` for each role,
`send_message` or `followup_task` for handoffs and repairs, and `wait_agent` to
receive completion. QA must be a different agent from Engineer. Wait for each
role to finish before dispatching its dependent role; do not simulate roles in
the main session or overlap Engineer writes with QA verification.

Each dispatch must include:

- The role document's contents (or its exact path with an instruction to read it),
  the issue URL and current body, and the applicable product/process documents.
- Repository path, designated non-main branch, starting commit hash, and recorded
  pre-existing changes. Each agent checks branch, HEAD, and working-tree status
  before acting and reports unexpected changes without discarding them.
- Authorized issue writes, permitted local commits, scope/constraints, and the
  expected role deliverable. Do not give QA Engineer's write permissions.
- Relevant prior role output. Give QA the Engineer's final commit hash and report;
  give Engineer the complete QA findings on repair attempts.

Use the same designated branch throughout. PM receives the starting revision;
Engineer reports its new revision; QA verifies that exact new revision. No agent
switches branch or changes the revision under another agent. Preserve known
unrelated changes and disclose them with verification evidence; if they affect
the tested behavior, resolve that ambiguity before attributing PASS to a commit.

Native dispatch is preferred; role Markdown files are instructions, not installed
agent configurations. Do not add `.codex/agents` files, install tools, change
credentials, or relax sandbox/approval settings to make the workflow run. If a
future session lacks dispatch or required access, report the actual limitation
instead of claiming a team ran.

## Orchestrator lifecycle

1. Select only the issue allowed by the current run instruction. Confirm its
   mapping, dependencies, write authorization, and designated non-main branch.
   Inspect the working tree; preserve existing work. If authorized to create the
   branch, do so before implementation, using the `codex/` prefix by default.
2. Dispatch PM to groom the issue. Wait for the updated issue and PM's readiness
   report. Do not skip grooming or send unresolved product decisions to Engineer.
3. Dispatch Engineer against that groomed issue. Wait for its implementation,
   tests, local commit hashes, and issue comment when authorized. It stays open.
4. Dispatch a separate QA agent to inspect and independently test the reported
   revision against every acceptance criterion. Collect its evidence and verdict.
5. On FAIL, send the findings to Engineer for repair and additional local commits,
   then dispatch QA again against the new hash. Continue without routine handoff
   or retry approval. Do not impose a fixed two-attempt limit or weaken criteria.
6. On PASS for the current revision, report `READY FOR HUMAN PUSH / MERGE`, with
   the issue link, branch, verified hash, files changed, criteria evidence, test
   commands/results, and unresolved limitations. Leave the issue open.
7. Wait for the user's integration decision. A local PASS is not a push, merge,
   or issue closure. Do not advance to dependent work until integration is
   confirmed and the current run instruction permits the next issue.

Escalate genuine product conflicts, unavailable capabilities or permissions,
explicit resource limits, or repeated failures without progress. Include the
evidence, attempts, and specific decision needed. A verification block is
`BLOCKED / NOT VERIFIED`, never PASS. If the implementation revision or criteria
change after QA, its verdict does not cover those changes; dispatch QA again.

## Testing and Git boundaries

- Engineer writes tests for changed behavior, runs relevant tests, and runs the
  full suite: `uv run python manage.py test`. QA independently runs the full
  suite and any checks needed to assess every criterion, including regressions.
- Use Django's built-in test runner. Do not introduce pytest or dependencies.
- Engineer is authorized to make meaningful local commits for the dispatched
  issue on the designated non-main branch. Never commit directly to `main`.
- Inspect unstaged and staged diffs, stage only intended issue changes, and
  inspect `git diff --cached` before committing. Do not include unrelated work
  or the uncommitted workflow setup files in implementation commits.
- No push, merge, rebase, amendment of existing commits, or history rewriting
  without separate explicit user authorization. Prefer additional fix commits.
- QA records the actual verified local commit hash. It does not fix application
  code, edit checked-in tests, commit, or weaken criteria. Ordinary test-generated
  temporary artifacts are allowed; report unexpected working-tree changes.
- No role may describe local commits as pushed or merged. Keep issues open until
  the user's integration/closure instruction authorizes otherwise. Avoid commit
  messages that automatically close issues on a later merge.

## Migration state and pilot

The five task-to-issue mappings and dependency links have been verified. See the
[index in backlog.md](../backlog.md#task-to-issue-index) for their actual URLs.
The original task sections remain unchanged; migration is not PM grooming.

Workflow setup and migration-document changes remain uncommitted for inspection.
The migration authorization covers migration issue writes only; it does not
authorize PM grooming, implementation, or the Task 4 pilot. A later workflow run
requires its own instruction and issue-write authorization.

The first pilot selects only the issue mapped to Task 4. Pass the earlier Task 4
preparation report to PM if available: it contains a proposed implementation and
test scenarios, not implemented work or test evidence. Preserve its attention to
creation/assignment cases, separate edit roles, Completed read-only behavior,
crafted invalid requests, unchanged persisted data, and Tasks 1–3 regressions.
Task 4 reuses Current Member with minimal create/detail/edit navigation; deletion,
claiming, status transitions, Undo completion, board filters/KPIs, History, Reuse,
and authentication remain outside that pilot.

For a separately authorized pilot, the user can use:

> Run only the GitHub issue mapped to Task 4 under `_docs/process.md`.
> Resolve its real issue link from `backlog.md`; if migration is incomplete,
> report that blocker and do not start implementation. Use `codex/task-4` as the
> designated working branch; create it from the current accepted revision if it
> does not exist, preserving unrelated work and uncommitted setup files. I
> authorize PM to edit that issue and Engineer/QA to comment on it for this run;
> propose new follow-up issues without creating them. Dispatch actual separate
> PM, Engineer, and QA subagents using their Markdown instructions. Give PM the
> prior Task 4 preparation report as proposal input if available. Engineer may
> make local implementation/fix commits; QA must verify the resulting hash.
> Continue repairs and independent QA without routine approval requests. On
> PASS, report READY FOR HUMAN PUSH / MERGE and leave the issue open. Do not
> push, merge, close the issue, commit setup files, or advance to Tasks 5–8.

# Shared Household Chores MVP — Implementation Backlog

Tasks are ordered by dependency. Each task is intended to fit one focused coding-agent session.

## Task 1 — Bootstrap Django and prove the baseline

### Goal

Create the Django project and a single application package, with the smallest runnable configuration and test setup needed for later work.

### Acceptance Criteria

- The repository contains a Django project and one Django app for the household-chore functionality.
- The app is registered in Django settings and the project starts with Django's development server using the documented command.
- The initial Django migrations apply successfully to a clean local database.
- Automated tests use Django's built-in test runner.
- A single minimal smoke test proves that Django can load the app, and the full Django test command `uv run python manage.py test` passes.
- The README (or an equivalent short developer note) states the commands to install dependencies, migrate, run the server, and run tests, including `uv run python manage.py test` as the documented full test command.

### Out of Scope

- Household, member, or chore models.
- User-facing feature pages or workflows.
- Authentication, authorization, and current-member selection.
- Pytest or another alternative test runner unless a later approved task explicitly requires it.
- Production deployment configuration or styling.

## Task 2 — Add the household, member, and chore domain model

### Goal

Persist the one-household MVP data model and its core invariants so later UI tasks can rely on a tested domain foundation.

### Acceptance Criteria

- Migrations create `Household`, `Member`, and `Chore` records and their relationships.
- The application supports one household containing multiple members, with exactly one member designated as leader.
- A documented local/development bootstrap path creates the initial single `Household` and `Leader` when starting from a clean database.
- A chore stores a required title and creator; optional description, assignee, and due date; an `Open`, `In Progress`, or `Completed` status; and automatically managed creation and completion timestamps.
- New chores default to `Open`, and invalid status values are rejected.
- Completing a chore records `completed_at`; a chore that is not completed has no completion timestamp.
- Overdue is implemented as a derived condition: `due_date` is before today and status is not `Completed`.
- Model/domain tests cover required and optional fields, leader invariants, status choices, completion timestamps, and overdue boundary cases.

### Out of Scope

- Pages, forms, current-member selection, and member management actions.
- Signup, onboarding, authentication, or a household-creation UI.
- Chore permissions, claiming, board metrics, history, or reuse.
- Multiple-household behavior.

### Dependencies

- Task 1.

## Task 3 — Add current-member selection and leader-only member management

### Goal

Let a visitor choose which household member they are acting as, and let the leader maintain the household's regular members without adding real authentication.

### Acceptance Criteria

- A visible `Current Member` selector lists active members from the single household; deactivated members do not appear.
- Selecting a member stores that choice in the session and subsequent requests consistently use it as the acting member.
- If the selected member no longer exists or has been deactivated, the session selection is cleared and the user is prompted to choose another member instead of receiving a server error.
- The leader can add a regular member, rename any member, and deactivate a regular member.
- The leader cannot be deactivated.
- A regular member with one or more assigned, non-completed chores cannot be deactivated; the leader must first reassign or unassign those active chores.
- A rejected deactivation does not change the member or any chores, does not automatically reassign or unassign chores, and does not change any chore's workflow status.
- Completed historical chores assigned to a regular member do not block that member's deactivation.
- A deactivated member cannot be selected as the assignee for a new chore.
- Deactivation preserves historical creator and assignee references, and existing historical chores continue to display the deactivated member.
- A regular member cannot access or submit member-management actions; direct requests are rejected without changing data.
- Request and domain tests cover selection persistence, successful and forbidden add/rename/deactivate operations, leader protection, blocking deactivation for active assignments, successful deactivation when only completed assignments remain, rejection without mutation, assignee choices, and preservation and display of historical references.

### Out of Scope

- Passwords, accounts, login/logout, invitations, or multiple roles.
- Multiple households.
- Physically deleting members through the normal member-management flow.
- Chore creation or workflow actions.

### Dependencies

- Task 2.

## Task 4 — Create, view, and edit chores with MVP permissions

### Goal

Implement the basic chore forms and enforce who may edit a chore based on the selected current member.

### Acceptance Criteria

- Any selected member can create a chore with a title, optional description, optional assignee who is active and belongs to the household, and optional due date.
- Creation records the selected member as creator and always creates the chore with status `Open`.
- A chore detail view is available to every member of the household.
- While a chore is `Open` or `In Progress`, the creator, assignee, and household leader can edit its title, description, assignee, and due date; any new or changed assignee must be active and belong to the household.
- While a chore is `Completed`, its normal editable fields are read-only for every member, including the creator, assignee, and household leader; direct normal-edit requests are rejected without changing the chore.
- A member who is not the creator, assignee, or leader can view the chore but cannot access or submit its edit action; a direct request is rejected without changing data.
- Assignee selectors for creation and editing show only active members of the household.
- Server-side validation rejects missing required data, an assignee outside the single household, and a deactivated assignee during creation, editing, or reassignment.
- Request tests cover unassigned, self-assigned, and other-active-member-assigned creation; assignment and reassignment to active members; rejected creation and editing with outside-household or deactivated assignees; selector contents; every allowed and denied edit role; and rejected normal edits to completed chores by the creator, assignee, and leader.

### Out of Scope

- Claiming chores or changing their status.
- Board filters and progress indicators.
- Completed-chore history and reuse.

### Dependencies

- Task 3.

## Task 5 — Implement claiming, status transitions, and Undo completion

### Goal

Support the active chore workflow from unassigned `Open` work through `In Progress` to `Completed`, plus the explicit correction for accidental completion.

### Acceptance Criteria

- Any selected member can claim an `Open`, unassigned chore; claiming sets that member as assignee and leaves the status `Open`.
- An already assigned, `In Progress`, or `Completed` chore cannot be claimed, and a rejected claim does not mutate it.
- Only the current assignee or the household leader can perform the forward transitions `Open` to `In Progress` and `In Progress` to `Completed`.
- After completion, the current assignee or household leader can use an explicit `Undo completion` action that changes the chore from `Completed` to `In Progress`.
- While a chore is `Completed`, its normal editable fields are read-only and `Undo completion` by the current assignee or household leader is the only permitted mutation.
- Undoing completion clears `completed_at` and returns the same chore to the active workflow, where the normal active-chore editing and permission rules apply again.
- A creator who is neither the current assignee nor the household leader retains the Task 4 field-edit permissions but cannot perform forward status transitions or undo completion.
- Unauthorized forward-transition and undo requests are rejected without changing the chore.
- Other backward, invalid, or skipped transitions remain rejected without changing data, including `In Progress` to `Open` and arbitrary reopening to another status.
- Completing a chore sets `completed_at` once; non-completion transitions do not set it.
- The detail UI exposes only actions valid for the selected member and current chore state.
- Request and domain tests cover successful claims, competing/invalid claims, every valid forward transition, successful undo by the current assignee, successful undo by the leader, rejected unauthorized undo, rejection of all other mutations while completed, clearing `completed_at`, return to the active workflow with normal edit permissions restored, other invalid backward transitions, permissions, and timestamps.

### Out of Scope

- General backward transitions, including `In Progress` to `Open` and arbitrary reopening to another status, except for the explicit `Undo completion` correction from `Completed` to `In Progress`.
- Additional or custom statuses.
- Automatic recurring chores, notifications, or reminders.
- History reuse.

### Dependencies

- Task 4.

## Task 6 — Build the shared active board, member filter, and indicators

### Goal

Provide the household's shared operational view with the two progress indicators defined by the MVP.

### Acceptance Criteria

- The board shows all non-completed chores for the single household and excludes completed chores.
- Chores with no assignee remain visible on the unfiltered board.
- Filtering by a member shows active chores assigned to that member; clearing the filter restores the full active board.
- Overdue chores are visibly identifiable using the derived overdue rule, not a new status.
- `Overdue Chores Count` equals the number of chores whose due date is before today and whose status is not `Completed`.
- The current week is defined as Monday through Sunday.
- `This Week Completion Rate` includes only chores due within that current week, with completed eligible chores as the numerator and all eligible chores as the denominator.
- Chores without a due date are excluded from the weekly calculation.
- If no chores are due in the current week, the indicator displays `No chores due this week` instead of a percentage.
- Both indicators remain household-level and unchanged by the member filter.
- Date-controlled tests cover Monday-Sunday boundaries, no-due-date chores, overdue rules, the no-eligible-chores message, active/completed visibility, and filtering.

### Out of Scope

- Per-member metrics, charts, points, badges, streaks, or leaderboards.
- Calendar integration and notifications.
- History and reuse.

### Dependencies

- Task 5.

## Task 7 — Add completed history and chore reuse

### Goal

Move completed work into a history view and allow any selected member to use a historical chore as the starting point for a new chore.

### Acceptance Criteria

- The History view lists chores whose current status is `Completed` for the household and does not list active chores.
- Completed chores no longer appear on the active board but remain viewable in History with their stored details and completion timestamp.
- If `Undo completion` is used, the same chore becomes `In Progress`, leaves History, returns to the active board, and follows the normal active-chore rules.
- Reuse is available for genuinely completed historical chores and is distinct from undo: undo corrects the same chore, while reuse creates a new chore record.
- Any selected member can start reuse from a historical chore and receives a form prefilled with its title, description, and due date.
- If the historical chore's assignee is active, that assignee is prefilled; if the assignee has been deactivated, the reuse form leaves the chore unassigned.
- Only active members can be assigned to the newly reused chore.
- Before submitting, the user can change all normal editable chore fields, including assignee and due date.
- Submitting reuse creates a distinct chore whose creator is the selected member, whose status is `Open`, and whose `completed_at` is empty.
- Reuse does not mutate the historical source chore.
- Request tests cover history/board separation by current status, removal from History and return to the active board after undo, reuse with active and deactivated historical assignees, edited reuse, active-only assignment, the new record's identity and timestamps, and preservation of the source.

### Out of Scope

- Automatic recurrence or scheduled duplication.
- Bulk reuse, archival deletion, exports, notifications, or calendar integration.
- Any feature listed as out of scope in the MVP specification.

### Dependencies

- Task 6.

## Task 8 — Verify the complete MVP against the specification

### Goal

Independently verify the complete system against the approved MVP specification without adding new functionality.

### Acceptance Criteria

- Every acceptance criterion in `_docs/plan.md` is mapped to an implementation or automated test.
- The full test suite passes.
- An end-to-end workflow test covers selecting a member, creating or claiming a chore, progressing it through the valid statuses, completing it, finding it in History, and reusing it as a new active chore.
- Only active household members can be assigned during chore creation, editing, and reassignment; selectors and server-side rejection of deactivated or outside-household members are verified.
- Member and leader permission boundaries are verified, including member-management, chore-editing, forward status-transition, and `Undo completion` permissions.
- Verification confirms that completed chores' normal editable fields are read-only and that authorized `Undo completion` is their only permitted mutation; unauthorized undo and normal-edit requests do not mutate the chore.
- Verification confirms that `Undo completion` changes `Completed` to `In Progress`, clears `completed_at`, returns the chore to the active board, and removes it from History without creating a new chore.
- The weekly completion indicator and overdue chores count are verified against their defined date and status rules.
- The application starts successfully by following the documented setup instructions from a clean local/development environment.
- The README commands match the commands that actually install dependencies, initialize data, run migrations, start the application, and run tests.
- Verification confirms that no features outside the approved MVP scope have been introduced.

### Out of Scope

- New product functionality.
- Unnecessary refactoring.
- Deployment or production infrastructure.

### Dependencies

- Tasks 1 through 7.

# Shared Household Chores — MVP Specification

## 1. Goal

Build a simple shared household chore management application.

The application should help members of one household create, assign, claim,
track, complete, review, and reuse household chores.

The MVP is designed for families or roommates sharing household responsibilities.

Future versions may support multiple households or small domestic-service teams,
but these are outside the scope of the current MVP.


## 2. Users

The application manages one Household.

A Household contains multiple Members.

One Member is designated as the Leader.

There is no real user authentication in the MVP.
Instead, the user selects the current member from a "Current Member" selector.


## 3. Core Features

### Feature 1 — Household and Member Management

The household contains multiple members and one leader.

The Leader can:
- add members
- rename members
- remove members

The MVP supports only one household.


### Feature 2 — Create, Assign, and Claim Chores

Any member can create a chore.

When creating a chore, the creator may:
- assign it to themselves
- assign it to another member
- leave it unassigned

Any member may claim an unassigned chore.

A chore moves through these statuses:

Open → In Progress → Completed

Rules:

- Open + unassigned: available for any member to claim
- Open + assigned: assigned but not started
- In Progress: work has started
- Completed: work is finished

A chore may be edited by:
- its creator
- its assignee
- the household leader

Other members may view the chore but may not edit it.


### Feature 3 — Due Dates, History, and Reuse

A chore may optionally have a due date.

If a chore has a due date earlier than today and is not Completed,
it is considered Overdue.

Overdue is a derived condition, not a separate chore status.

Completed chores leave the active board and appear in History.

Users can reuse a chore from History.

When reusing a chore:
- the main chore information is copied
- the user may change the assignee
- the user may change the due date
- other editable fields may be changed before creation
- a new chore record is created
- the new chore always starts with status Open


### Feature 4 — Shared Board and Progress Tracking

All members see the same shared household board.

The board shows active chores.

Users can filter chores by member.

The board displays two household-level indicators:

1. This Week Completion Rate
2. Overdue Chores Count

This Week Completion Rate only includes chores whose due date falls within
the current week.

Chores without a due date are shown on the board but are not included in
the weekly completion-rate calculation.

Overdue Chores Count includes chores where:

due_date < today
AND
status != Completed


## 4. Chore Data

Each chore contains:

- title — required
- description — optional
- creator — automatically recorded
- assignee — optional
- status — Open / In Progress / Completed
- due_date — optional
- created_at — automatically recorded
- completed_at — automatically recorded when completed


## 5. Main User Workflow

1. User selects the current member.
2. User opens the shared household board.
3. User can create a new chore.
4. The chore may be assigned or left unassigned.
5. An unassigned chore may be claimed by another member.
6. The assignee moves the chore from Open to In Progress.
7. The chore is marked Completed when finished.
8. Completed chores move to History.
9. A historical chore may be reused to create a new chore.


## 6. Permissions

Leader:
- manage members
- create chores
- edit chores they are allowed to edit
- edit any chore in the household

Regular member:
- create chores
- claim unassigned chores
- edit chores they created
- edit chores assigned to them
- view all household chores

There is no real authentication or account system in the MVP.


## 7. Out of Scope

The MVP will NOT include:

- real authentication or passwords
- invitations by email
- multiple households
- users belonging to multiple households
- domestic-service-company management
- billing or payment
- automatic recurring chore scheduling
- notifications or reminders
- calendar integration
- points, badges, streaks, or member leaderboards
- complex role or permission systems


## 8. Acceptance Criteria

The MVP is successful if:

1. The leader can add, rename, and remove household members.
2. A member can create a chore.
3. A chore can be assigned to a member or left unassigned.
4. A member can claim an unassigned chore.
5. A chore can move through Open, In Progress, and Completed.
6. Creator, assignee, and leader can edit the appropriate chores.
7. Other members cannot edit chores they are not permitted to modify.
8. A chore may have an optional due date.
9. Overdue chores are correctly identified.
10. Completed chores appear in History rather than the active board.
11. A historical chore can be reused to create a new Open chore.
12. The shared board can filter chores by member.
13. The board correctly shows this week's completion rate.
14. The board correctly shows the number of overdue chores.
15. Chores without due dates are excluded from the weekly completion-rate calculation.
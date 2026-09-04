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
Instead, the user selects an active member from a "Current Member" selector.


## 3. Core Features

### Feature 1 — Household and Member Management

The household contains multiple members and one leader.

The Leader can:
- add members
- rename members
- deactivate regular members

Removing a regular member means deactivating them, not physically deleting
their record.

The Leader cannot be deactivated.

A regular member with one or more assigned, non-completed chores cannot be
deactivated. The Leader must first reassign or unassign those active chores.
A failed deactivation does not change the member, any chores, or any chore's
workflow status. Deactivation does not automatically reassign chores.

Completed historical chores do not block deactivation.

Deactivated members:
- do not appear in the Current Member selector
- cannot be selected as assignees when creating, editing, or reassigning chores
- remain visible as creators or assignees on historical chores

Historical creator and assignee references are preserved after deactivation.

The MVP supports only one household.


### Feature 2 — Create, Assign, and Claim Chores

Any member can create a chore.

When creating a chore, the creator may:
- assign it to themselves
- assign it to another active member
- leave it unassigned

A chore may only be assigned to an active member of the same household. This
rule applies when creating, editing, or reassigning a chore. Assignee selectors
only show active household members, and server-side validation rejects members
outside the household and deactivated members.

Any member may claim an unassigned chore.

A chore moves through these statuses:

Open → In Progress → Completed

Rules:

- Open + unassigned: available for any member to claim
- Open + assigned: assigned but not started
- In Progress: work has started
- Completed: work is finished

A chore's normal editable fields may be edited while it is Open or In Progress by:
- its creator
- its assignee
- the household leader

Other members may view the chore but may not edit it.

Only the current assignee or the household Leader may perform valid forward
workflow transitions:

Open → In Progress → Completed

A creator who is not also the current assignee or Leader may edit the normal
chore fields permitted above, but may not change the chore's workflow status.

While a chore is Completed, its normal editable fields are read-only. The only
permitted mutation is an explicit `Undo completion` action by the current
assignee or household Leader. This changes the same chore from Completed to In
Progress and clears `completed_at`. The chore then follows the normal
active-chore editing and permission rules again.

A creator who is neither the current assignee nor Leader cannot undo
completion. Unauthorized undo requests are rejected without changing the
chore. Other backward transitions remain disallowed: In Progress cannot move
back to Open, arbitrary reopening to another status is not supported, and no
additional statuses are introduced.


### Feature 3 — Due Dates, History, and Reuse

A chore may optionally have a due date.

If a chore has a due date earlier than today and is not Completed,
it is considered Overdue.

Overdue is a derived condition, not a separate chore status.

History contains chores whose current status is Completed. Completed chores
leave the active board and appear in History.

If `Undo completion` is used, the chore leaves History and returns to the active
board with status In Progress.

Users can reuse a genuinely completed chore from History.

`Undo completion` and Reuse are distinct: undo corrects an accidental
completion on the same chore, while reuse creates a new chore record from a
historical chore.

When reusing a chore:
- the main chore information is copied
- if the previous assignee is active, that assignee is prefilled
- if the previous assignee is deactivated, the new chore is left unassigned
- only active members may be assigned to the new chore
- the user may change the assignee
- the user may change the due date
- other editable fields may be changed before creation
- a new chore record is created
- the new chore always starts with status Open
- the historical source chore remains unchanged


### Feature 4 — Shared Board and Progress Tracking

All members see the same shared household board.

The board shows active chores.

Users can filter chores by member.

The board displays two household-level indicators:

1. This Week Completion Rate
2. Overdue Chores Count

The current week is Monday through Sunday.

This Week Completion Rate only includes chores whose due date falls within
the current Monday-Sunday week. Completed eligible chores are the numerator,
and all eligible chores are the denominator.

Chores without a due date are shown on the board but are not included in
the weekly completion-rate calculation.

If no chores are due during the current week, the board displays:

`No chores due this week`

This state is not represented as 0%.

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
  and cleared when completion is undone


## 5. Main User Workflow

1. User selects the current member.
2. User opens the shared household board.
3. User can create a new chore.
4. The chore may be assigned or left unassigned.
5. An unassigned chore may be claimed by another member.
6. The current assignee or Leader moves the chore from Open to In Progress.
7. The current assignee or Leader marks the chore Completed when finished.
8. Completed chores move to History.
9. The current assignee or Leader may undo an accidental completion, returning
   the same chore to In Progress and the active board.
10. A genuinely completed historical chore may be reused to create a new chore.


## 6. Permissions

Leader:
- manage members
- create chores
- edit chores they are allowed to edit
- edit any Open or In Progress chore in the household
- perform valid forward status transitions on any chore
- undo completion on any completed chore

Regular member:
- create chores
- claim unassigned chores
- edit Open or In Progress chores they created
- edit Open or In Progress chores assigned to them
- perform valid forward status transitions only on chores currently assigned to them
- undo completion only on completed chores currently assigned to them
- view all household chores

A regular member who created a chore but is not its current assignee may edit
its normal fields but may not change its workflow status or undo completion.

While a chore is Completed, its normal editable fields are read-only for every
member, including the Leader. The only permitted mutation is `Undo completion`
by the current assignee or Leader. After undo returns it to In Progress, the
normal active-chore editing and permission rules apply again.

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
- physical deletion of members through normal member management
- general backward workflow transitions, except for the explicit `Undo completion`
  correction from Completed to In Progress
- moving a chore from In Progress back to Open or arbitrarily reopening it to
  another status
- additional chore statuses
- deployment or production infrastructure


## 8. Acceptance Criteria

The MVP is successful if:

1. The Leader can add and rename members and deactivate regular members, but the Leader cannot be deactivated.
2. A member can create a chore.
3. A chore can be assigned to an active member of the household or left unassigned when created, edited, or reassigned; assignee selectors show only active members, and server-side validation rejects deactivated members and members outside the household.
4. A member can claim an unassigned chore.
5. Only the current assignee or Leader can move a chore forward through Open, In Progress, and Completed.
6. Creator, assignee, and Leader can edit the appropriate normal chore fields while a chore is Open or In Progress; those fields are read-only while it is Completed.
7. Other members cannot edit chores they are not permitted to modify.
8. A chore may have an optional due date.
9. Overdue chores are correctly identified.
10. History contains chores whose current status is Completed; undoing completion changes the same chore to In Progress, clears `completed_at`, removes it from History, and returns it to the active board.
11. A historical chore can be reused to create a new Open chore without changing the source; an active previous assignee is prefilled, while a deactivated previous assignee leaves the new chore unassigned.
12. The shared board can filter chores by member.
13. The board correctly calculates this week's completion rate for the current Monday-Sunday week using completed eligible chores over all eligible chores.
14. The board correctly shows the number of overdue chores.
15. Chores without due dates are excluded from the weekly completion-rate calculation, and a week with no eligible chores displays `No chores due this week` rather than 0%.
16. Deactivated members do not appear in the Current Member selector and cannot be assigned to new chores.
17. A member with assigned, non-completed chores cannot be deactivated until those chores are reassigned or unassigned; a rejected attempt changes neither the member nor any chore or status.
18. Completed chores do not block deactivation, and historical creator and assignee references to a deactivated member remain preserved and visible.
19. A creator who is neither the current assignee nor Leader cannot change workflow status or undo completion.
20. While a chore is Completed, `Undo completion` by the current assignee or Leader is its only permitted mutation; it moves the chore to In Progress, after which normal active-chore editing rules apply again, and unauthorized undo or normal-edit requests are rejected without mutation.
21. Other backward transitions, including In Progress to Open and arbitrary reopening to another status, remain unavailable, and no additional statuses are introduced.

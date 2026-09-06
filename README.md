# Shared Household Chores

This repository contains the minimal Django baseline for the Shared Household
Chores MVP. The Django project package is `household_chores`, and the single
application package is `chores`.

## Prerequisites

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)

## Install dependencies

```shell
uv sync
```

## Apply migrations

```shell
uv run python manage.py migrate
```

## Create the initial household and leader

After migrating a clean local/development database, bootstrap the MVP's single
household and its leader with:

```shell
uv run python manage.py bootstrap_household \
  --household-name "My Household" \
  --leader-name "Household Leader"
```

Running the command again leaves the existing household unchanged.

## Run the development server

```shell
uv run python manage.py runserver
```

The development server starts at <http://127.0.0.1:8000/> by default.

## Try creating and editing chores

Select the household Leader in **Current Member** and use **Manage members** to
add regular members. Select the member you want to act as, then choose **Create
chore**. Enter a title, optionally fill in the description and due date, and
choose an active assignee or **Unassigned**. Saving opens the chore's details.

The home page shows the household's active board and links to chore details.
**Filter by member** selects chores by their current assignee without changing
Current Member. **Clear filter** restores all active chores. The **This Week
Completion Rate** and **Overdue Chores Count** always describe the whole household.
The completion rate counts chores due Monday through Sunday, including completed
chores; without eligible chores it shows **No chores due this week**. Overdue
means due before today and not completed.

**Edit chore** is available to
the creator, current assignee, or Leader while the chore is Open or In Progress.
Other members can view its details. Completed chores' normal fields are read-only.

On an Open, unassigned chore, any selected member can choose **Claim**. The
current assignee or Leader can choose **Start work**, then **Complete chore**.
The Leader can also progress an unassigned chore. Completion shows its timestamp.
The current assignee or Leader can use **Undo completion** to return the same
chore to In Progress, clear the completion timestamp, and restore normal editing.
Completion removes the chore from the active board; Undo returns it. Until
History is available, keep the completed chore's detail URL to revisit it.

## Run tests

```shell
uv run python manage.py test
```

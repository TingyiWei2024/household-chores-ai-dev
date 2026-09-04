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

## Run the development server

```shell
uv run python manage.py runserver
```

The development server starts at <http://127.0.0.1:8000/> by default.

## Run tests

```shell
uv run python manage.py test
```

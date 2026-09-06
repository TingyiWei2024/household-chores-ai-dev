"""Household-wide board indicators, independent of the visible member filter."""

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from chores.models import Chore


def household_indicators(household):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    due_this_week = Q(due_date__range=(week_start, week_end))
    completed = Q(status=Chore.Status.COMPLETED)
    counts = Chore.objects.filter(creator__household=household).aggregate(
        week_total=Count("pk", filter=due_this_week),
        week_completed=Count("pk", filter=due_this_week & completed),
        overdue_count=Count("pk", filter=Q(due_date__lt=today) & ~completed),
    )
    return {
        **counts,
        "week_start": week_start,
        "week_end": week_end,
        "completion_rate": (
            100 * counts["week_completed"] / counts["week_total"]
            if counts["week_total"] else None
        ),
    }

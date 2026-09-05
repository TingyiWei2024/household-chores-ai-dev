"""Helpers for the MVP's session-backed acting member."""

from django.core.exceptions import ValidationError

from chores.models import Household, Member

CURRENT_MEMBER_SESSION_KEY = "current_member_id"


def get_single_household():
    """Return the household used by the single-household MVP, if initialized."""
    return Household.objects.select_related("leader").first()


def load_current_member(request, household):
    """Load an active selected member or clear an invalid/stale selection."""
    selected_id = request.session.get(CURRENT_MEMBER_SESSION_KEY)
    if selected_id is None or household is None:
        return None

    try:
        member = Member.objects.filter(
            pk=selected_id,
            household=household,
            is_active=True,
        ).first()
    except (ValidationError, ValueError):
        member = None

    if member is None:
        request.session.pop(CURRENT_MEMBER_SESSION_KEY, None)

    return member

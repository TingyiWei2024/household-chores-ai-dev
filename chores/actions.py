"""Explicit, guarded workflow actions for the single household."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from chores.models import Chore, Member


ACTION_LABELS = {
    "claim": "Claim",
    "start": "Start work",
    "complete": "Complete chore",
    "undo_completion": "Undo completion",
}

FORWARD_AND_UNDO = {
    "start": (Chore.Status.OPEN, Chore.Status.IN_PROGRESS),
    "complete": (Chore.Status.IN_PROGRESS, Chore.Status.COMPLETED),
    "undo_completion": (Chore.Status.COMPLETED, Chore.Status.IN_PROGRESS),
}


def available_chore_actions(chore, member):
    """Return the named actions this member may see on the current detail."""
    if (
        member is None
        or not member.is_active
        or member.household_id != chore.creator.household_id
    ):
        return []

    actions = []
    if chore.status == Chore.Status.OPEN and chore.assignee_id is None:
        actions.append("claim")
    if member.pk == chore.assignee_id or member.is_leader:
        actions.extend(
            action
            for action, (source, target) in FORWARD_AND_UNDO.items()
            if chore.status == source
        )
    return [(action, ACTION_LABELS[action]) for action in actions]


def perform_chore_action(*, chore, member, action):
    """Validate persisted identity/state and atomically change only action fields.

    Conditional updates prevent a stale claim or workflow request from replacing
    another request's assignment or state, including on SQLite where row locks
    via select_for_update are unavailable. They deliberately preserve all normal
    fields and historical references; Undo is not a reassignment operation.
    """
    if action not in ACTION_LABELS:
        raise ValidationError("Unknown chore action.")
    if member is None:
        raise PermissionDenied("Choose an active Current Member.")
    actor = Member.objects.filter(pk=member.pk, is_active=True).first()
    if actor is None:
        raise PermissionDenied("Choose an active Current Member.")
    stored = Chore.objects.select_related("creator").get(
        pk=chore.pk, creator__household_id=actor.household_id
    )

    if action == "claim":
        if stored.status != Chore.Status.OPEN or stored.assignee_id is not None:
            raise ValidationError("Only an Open, unassigned chore can be claimed.")
        changes = {"assignee_id": actor.pk}
    else:
        if actor.pk != stored.assignee_id and not actor.is_leader:
            raise PermissionDenied("Only the current assignee or Leader may do this.")
        source, target = FORWARD_AND_UNDO[action]
        if stored.status != source:
            raise ValidationError("This action is not valid for the chore's status.")
        changes = {
            "status": target,
            "completed_at": timezone.now() if target == Chore.Status.COMPLETED else None,
        }

    updated = Chore.objects.filter(
        pk=stored.pk,
        creator_id=stored.creator_id,
        status=stored.status,
        assignee_id=stored.assignee_id,
        completed_at=stored.completed_at,
        creator__household__members__pk=actor.pk,
        creator__household__members__is_active=True,
    ).update(**changes)
    if not updated:
        raise ValidationError("The chore changed. Review its details and try again.")
    stored.refresh_from_db()
    return stored

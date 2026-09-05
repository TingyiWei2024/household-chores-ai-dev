"""Template context shared by the Task 3 pages."""

from chores.forms import CurrentMemberForm


def current_member(request):
    household = getattr(request, "household", None)
    member = getattr(request, "current_member", None)
    return {
        "current_household": household,
        "current_member": member,
        "current_member_form": CurrentMemberForm(
            household=household,
            initial={"member": member},
        ),
    }

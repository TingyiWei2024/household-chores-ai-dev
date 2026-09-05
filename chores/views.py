"""Views for current-member selection and member management."""

from functools import wraps

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from chores.current_member import CURRENT_MEMBER_SESSION_KEY
from chores.forms import CurrentMemberForm, MemberForm
from chores.models import Member


def leader_required(view_function):
    """Allow only the selected household leader to use a view."""

    @wraps(view_function)
    def wrapped(request, *args, **kwargs):
        if request.current_member is None:
            return redirect("chores:home")
        if not request.current_member.is_leader:
            raise PermissionDenied("Only the household leader may manage members.")
        return view_function(request, *args, **kwargs)

    return wrapped


def _household_or_404(request):
    if request.household is None:
        raise Http404("The household has not been initialized.")
    return request.household


def _member_management_context(request, **extra):
    household = _household_or_404(request)
    context = {
        "members": household.members.order_by("name", "pk"),
        "leader_id": household.leader_id,
    }
    context.update(extra)
    return context


@require_GET
def home(request):
    return render(request, "chores/home.html")


@require_POST
def set_current_member(request):
    form = CurrentMemberForm(
        request.POST,
        household=request.household,
    )
    if form.is_valid():
        request.session[CURRENT_MEMBER_SESSION_KEY] = str(
            form.cleaned_data["member"].pk
        )
        return redirect("chores:home")

    return render(
        request,
        "chores/home.html",
        {"current_member_form": form},
        status=400,
    )


@require_GET
@leader_required
def member_list(request):
    return render(
        request,
        "chores/member_list.html",
        _member_management_context(request),
    )


@require_http_methods(["GET", "POST"])
@leader_required
def member_add(request):
    household = _household_or_404(request)
    form = MemberForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        member = form.save(commit=False)
        member.household = household
        member.is_active = True
        member.save()
        return redirect("chores:member_list")

    return render(
        request,
        "chores/member_form.html",
        {"form": form, "form_title": "Add member"},
        status=400 if request.method == "POST" else 200,
    )


@require_http_methods(["GET", "POST"])
@leader_required
def member_rename(request, member_id):
    household = _household_or_404(request)
    member = get_object_or_404(Member, pk=member_id, household=household)
    form = MemberForm(
        request.POST if request.method == "POST" else None,
        instance=member,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("chores:member_list")

    return render(
        request,
        "chores/member_form.html",
        {"form": form, "form_title": f"Rename {member.name}"},
        status=400 if request.method == "POST" else 200,
    )


@require_POST
@leader_required
def member_deactivate(request, member_id):
    household = _household_or_404(request)
    member = get_object_or_404(Member, pk=member_id, household=household)

    try:
        member.deactivate()
    except ValidationError as error:
        return render(
            request,
            "chores/member_list.html",
            _member_management_context(
                request,
                deactivation_error=" ".join(error.messages),
            ),
            status=400,
        )

    return redirect("chores:member_list")

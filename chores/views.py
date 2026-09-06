"""Views for current-member selection, member management, and chores."""

from functools import wraps

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from chores.actions import available_chore_actions, perform_chore_action
from chores.board import household_indicators
from chores.current_member import CURRENT_MEMBER_SESSION_KEY
from chores.forms import BoardFilterForm, ChoreForm, CurrentMemberForm, MemberForm
from chores.models import Chore, Member


def current_member_required(view_function):
    """Prompt for an active Current Member before accessing chore pages."""

    @wraps(view_function)
    def wrapped(request, *args, **kwargs):
        if request.current_member is None:
            return redirect("chores:home")
        return view_function(request, *args, **kwargs)

    return wrapped


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


def _board_context(request):
    if request.current_member is None:
        return {"chores": Chore.objects.none()}
    board_filter = BoardFilterForm(request.GET, household=request.household)
    chores = Chore.objects.filter(
        creator__household=request.household
    ).exclude(status=Chore.Status.COMPLETED).select_related("assignee")
    if board_filter.is_valid():
        member = board_filter.cleaned_data["member"]
        if member is not None:
            chores = chores.filter(assignee=member)
    else:
        chores = chores.none()
    return {
        "chores": chores.order_by("-created_at", "-pk"),
        "board_filter": board_filter,
        "indicators": household_indicators(request.household),
    }


@require_GET
def home(request):
    context = _board_context(request)
    invalid_filter = "board_filter" in context and context["board_filter"].errors
    return render(
        request, "chores/home.html", context, status=400 if invalid_filter else 200
    )


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
        {**_board_context(request), "current_member_form": form},
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


def _household_chore_or_404(request, chore_id):
    return get_object_or_404(
        Chore.objects.select_related("creator", "assignee"),
        pk=chore_id,
        creator__household=_household_or_404(request),
    )


def _can_edit_chore(request, chore):
    member = request.current_member
    return chore.status in (Chore.Status.OPEN, Chore.Status.IN_PROGRESS) and (
        member.pk == chore.creator_id
        or member.pk == chore.assignee_id
        or member.pk == request.household.leader_id
    )


@require_http_methods(["GET", "POST"])
@current_member_required
def chore_create(request):
    form = ChoreForm(
        request.POST if request.method == "POST" else None,
        household=_household_or_404(request),
        instance=Chore(creator=request.current_member),
    )
    if request.method == "POST" and form.is_valid():
        chore = form.save()
        return redirect("chores:chore_detail", chore_id=chore.pk)

    return render(
        request,
        "chores/chore_form.html",
        {"form": form, "form_title": "Create chore"},
        status=400 if request.method == "POST" else 200,
    )


@require_GET
@current_member_required
def chore_detail(request, chore_id):
    chore = _household_chore_or_404(request, chore_id)
    return render(
        request,
        "chores/chore_detail.html",
        _chore_detail_context(request, chore),
    )


def _chore_detail_context(request, chore, **extra):
    return {
        "chore": chore,
        "can_edit": _can_edit_chore(request, chore),
        "workflow_actions": available_chore_actions(chore, request.current_member),
        **extra,
    }


@require_POST
@current_member_required
def chore_action(request, chore_id):
    chore = _household_chore_or_404(request, chore_id)
    try:
        if set(request.POST) - {"action", "csrfmiddlewaretoken"}:
            raise ValidationError("Workflow actions do not accept chore field changes.")
        perform_chore_action(
            chore=chore,
            member=request.current_member,
            action=request.POST.get("action"),
        )
    except Chore.DoesNotExist:
        raise Http404("The chore is no longer available.")
    except ValidationError as error:
        chore.refresh_from_db()
        return render(
            request,
            "chores/chore_detail.html",
            _chore_detail_context(
                request, chore, workflow_error=" ".join(error.messages)
            ),
            status=400,
        )
    return redirect("chores:chore_detail", chore_id=chore.pk)


@require_http_methods(["GET", "POST"])
@current_member_required
def chore_edit(request, chore_id):
    chore = _household_chore_or_404(request, chore_id)
    if not _can_edit_chore(request, chore):
        raise PermissionDenied("You may not edit this chore.")

    form = ChoreForm(
        request.POST if request.method == "POST" else None,
        household=request.household,
        instance=chore,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("chores:chore_detail", chore_id=chore.pk)

    return render(
        request,
        "chores/chore_form.html",
        {"form": form, "form_title": "Edit chore", "chore": chore},
        status=400 if request.method == "POST" else 200,
    )

"""Forms for current-member selection, members, and normal chore fields."""

from django import forms

from chores.models import Chore, Member


class CurrentMemberForm(forms.Form):
    member = forms.ModelChoiceField(
        queryset=Member.objects.none(),
        empty_label="Choose a member",
        label="Current Member",
    )

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)
        if household is not None:
            self.fields["member"].queryset = household.members.filter(
                is_active=True
            ).order_by("name", "pk")


class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ("name",)


class ChoreForm(forms.ModelForm):
    class Meta:
        model = Chore
        fields = ("title", "description", "assignee", "due_date")
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, household, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = household.members.filter(
            is_active=True
        ).order_by("name", "pk")
        self.fields["assignee"].empty_label = "Unassigned"


class BoardFilterForm(forms.Form):
    member = forms.ModelChoiceField(
        queryset=Member.objects.none(),
        required=False,
        empty_label="All members",
        label="Filter by member",
    )

    def __init__(self, *args, household, **kwargs):
        super().__init__(*args, auto_id="id_filter_%s", **kwargs)
        # Filtering is read-only: inactive historical assignees remain valid
        # filter choices, even though they cannot act or receive new assignments.
        self.fields["member"].queryset = household.members.order_by("name", "pk")

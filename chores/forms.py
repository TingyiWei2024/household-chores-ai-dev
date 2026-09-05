"""Forms for current-member selection and member management."""

from django import forms

from chores.models import Member


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

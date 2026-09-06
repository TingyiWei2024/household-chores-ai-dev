"""Task 4 request coverage for normal chore fields and permission boundaries."""

from datetime import date
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from chores.current_member import CURRENT_MEMBER_SESSION_KEY
from chores.models import Chore, Household, Member


class Task4TestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.household, cls.leader = Household.objects.create_with_leader(
            household_name="Home", leader_name="Alex Leader"
        )
        cls.creator = Member.objects.create(
            household=cls.household, name="Bailey Creator"
        )
        cls.assignee = Member.objects.create(
            household=cls.household, name="Casey Assignee"
        )
        cls.unrelated = Member.objects.create(
            household=cls.household, name="Drew Unrelated"
        )
        cls.inactive = Member.objects.create(
            household=cls.household, name="Erin Inactive", is_active=False
        )
        cls.other_household, cls.outsider = Household.objects.create_with_leader(
            household_name="Other Home", leader_name="Outside Member"
        )

    def setUp(self):
        # Keep the application's single household deterministic while providing
        # outside-household fixtures solely for crafted-request boundary checks.
        household_patch = patch(
            "chores.middleware.get_single_household", return_value=self.household
        )
        household_patch.start()
        self.addCleanup(household_patch.stop)
        self.select_member(self.creator)

    def select_member(self, member):
        session = self.client.session
        session[CURRENT_MEMBER_SESSION_KEY] = str(member.pk)
        session.save()

    def make_chore(self, **overrides):
        fields = {
            "title": "Clean the kitchen",
            "description": "Wipe the surfaces",
            "creator": self.creator,
            "assignee": self.assignee,
            "due_date": date(2026, 10, 15),
        }
        fields.update(overrides)
        return Chore.objects.create(**fields)

    def chore_data(self, **overrides):
        data = {
            "title": "Wash the dishes",
            "description": "Include the pans",
            "assignee": str(self.assignee.pk),
            "due_date": "2026-11-12",
        }
        data.update(overrides)
        return data

    def snapshot(self, chore):
        # Compare every stored field, including PKs, references, and timestamps.
        return Chore.objects.values().get(pk=chore.pk)

    def detail_url(self, chore):
        return reverse("chores:chore_detail", args=[chore.pk])

    def edit_url(self, chore):
        return reverse("chores:chore_edit", args=[chore.pk])


class ChoreNavigationAndSelectionTests(Task4TestCase):
    def test_selected_member_can_reach_create_detail_and_permitted_edit(self):
        chore = self.make_chore()
        response = self.client.get(reverse("chores:home"))
        self.assertContains(response, reverse("chores:chore_create"))
        self.assertContains(response, self.detail_url(chore))
        self.assertContains(
            self.client.get(self.detail_url(chore)), self.edit_url(chore)
        )
        self.assertEqual(self.client.get(self.edit_url(chore)).status_code, 200)
        self.assertEqual(
            self.client.session[CURRENT_MEMBER_SESSION_KEY], str(self.creator.pk)
        )

    def test_invalid_session_selections_prompt_without_any_chore_mutation(self):
        chore = self.make_chore()
        before = self.snapshot(chore)
        deleted = Member.objects.create(household=self.household, name="Deleted")
        deleted_id = str(deleted.pk)
        deleted.delete()
        selections = (
            None,
            deleted_id,
            str(self.inactive.pk),
            str(self.outsider.pk),
            "not-a-uuid",
            "",
            [],
            {},
        )
        targets = (
            ("get", reverse("chores:chore_create")),
            ("post", reverse("chores:chore_create")),
            ("get", self.detail_url(chore)),
            ("get", self.edit_url(chore)),
            ("post", self.edit_url(chore)),
        )
        for selection in selections:
            for method, url in targets:
                with self.subTest(selection=selection, method=method, url=url):
                    session = self.client.session
                    session.pop(CURRENT_MEMBER_SESSION_KEY, None)
                    if selection is not None:
                        session[CURRENT_MEMBER_SESSION_KEY] = selection
                    session.save()
                    response = getattr(self.client, method)(url, self.chore_data())
                    self.assertRedirects(response, reverse("chores:home"))
                    self.assertNotIn(CURRENT_MEMBER_SESSION_KEY, self.client.session)
                    self.assertContains(
                        self.client.get(reverse("chores:home")),
                        "Choose an active Current Member",
                    )
                    self.assertEqual(Chore.objects.count(), 1)
                    self.assertEqual(self.snapshot(chore), before)


class ChoreCreationTests(Task4TestCase):
    def test_regular_member_and_leader_can_create_all_assignment_cases(self):
        for actor in (self.creator, self.leader):
            for assignee in (None, actor, self.unrelated):
                with self.subTest(actor=actor.name, assignee=assignee):
                    self.select_member(actor)
                    start = timezone.now()
                    response = self.client.post(
                        reverse("chores:chore_create"),
                        self.chore_data(assignee=str(assignee.pk) if assignee else ""),
                    )
                    chore = Chore.objects.latest("pk")
                    self.assertRedirects(response, self.detail_url(chore))
                    self.assertEqual(chore.title, "Wash the dishes")
                    self.assertEqual(chore.description, "Include the pans")
                    self.assertEqual(chore.due_date, date(2026, 11, 12))
                    self.assertEqual(chore.assignee, assignee)
                    self.assertEqual(chore.creator, actor)
                    self.assertEqual(chore.status, Chore.Status.OPEN)
                    self.assertLessEqual(start, chore.created_at)
                    self.assertLessEqual(chore.created_at, timezone.now())
                    self.assertIsNone(chore.completed_at)
        self.assertEqual(Chore.objects.count(), 6)

    def test_optional_fields_may_be_omitted(self):
        response = self.client.post(
            reverse("chores:chore_create"), {"title": "Sweep"}
        )
        chore = Chore.objects.get()
        self.assertRedirects(response, self.detail_url(chore))
        self.assertEqual(chore.description, "")
        self.assertIsNone(chore.assignee)
        self.assertIsNone(chore.due_date)

    def test_creation_ignores_crafted_protected_fields(self):
        start = timezone.now()
        response = self.client.post(
            reverse("chores:chore_create"),
            self.chore_data(
                creator=str(self.outsider.pk),
                creator_id=str(self.outsider.pk),
                status=Chore.Status.COMPLETED,
                created_at="2000-01-01T01:02:03Z",
                completed_at="2000-01-02T01:02:03Z",
            ),
        )
        chore = Chore.objects.get()
        self.assertRedirects(response, self.detail_url(chore))
        self.assertEqual(chore.creator, self.creator)
        self.assertEqual(chore.status, Chore.Status.OPEN)
        self.assertLessEqual(start, chore.created_at)
        self.assertIsNone(chore.completed_at)


class ChoreDetailTests(Task4TestCase):
    def test_every_member_can_view_stored_details_in_every_state(self):
        for status in Chore.Status.values:
            chore = self.make_chore(status=status)
            for actor in (self.creator, self.assignee, self.leader, self.unrelated):
                with self.subTest(status=status, actor=actor.name):
                    self.select_member(actor)
                    response = self.client.get(self.detail_url(chore))
                    for value in (
                        chore.title,
                        chore.description,
                        self.creator.name,
                        self.assignee.name,
                        chore.get_status_display(),
                        "2026-10-15",
                        chore.created_at.isoformat(),
                    ):
                        self.assertContains(response, value)
                    if chore.completed_at:
                        self.assertContains(response, chore.completed_at.isoformat())

    def test_empty_optional_fields_have_visible_labels(self):
        chore = self.make_chore(assignee=None, description="", due_date=None)
        response = self.client.get(self.detail_url(chore))
        for label in ("Unassigned", "No description", "No due date"):
            self.assertContains(response, label)
        self.assertNotContains(response, "Completed at")

    def test_historical_creator_and_assignee_remain_visible_after_deactivation(self):
        chore = self.make_chore(status=Chore.Status.COMPLETED)
        before = self.snapshot(chore)
        self.select_member(self.leader)
        for member in (self.creator, self.assignee):
            response = self.client.post(
                reverse("chores:member_deactivate", args=[member.pk])
            )
            self.assertRedirects(response, reverse("chores:member_list"))
            member.refresh_from_db()
            self.assertFalse(member.is_active)
        response = self.client.get(self.detail_url(chore))
        self.assertContains(response, self.creator.name)
        self.assertContains(response, self.assignee.name)
        self.assertEqual(self.snapshot(chore), before)

    def test_outside_household_chore_is_not_exposed_or_mutated(self):
        chore = self.make_chore(
            title="Private outside chore", creator=self.outsider, assignee=self.outsider
        )
        before = self.snapshot(chore)
        for actor in (self.creator, self.leader):
            self.select_member(actor)
            self.assertNotContains(
                self.client.get(reverse("chores:home")), chore.title
            )
            for method, url in (
                ("get", self.detail_url(chore)),
                ("get", self.edit_url(chore)),
                ("post", self.edit_url(chore)),
            ):
                with self.subTest(actor=actor.name, method=method, url=url):
                    response = getattr(self.client, method)(url, self.chore_data())
                    self.assertEqual(response.status_code, 404)
                    self.assertNotContains(response, chore.title, status_code=404)
                    self.assertEqual(self.snapshot(chore), before)


class ChoreEditPermissionTests(Task4TestCase):
    def test_separate_creator_assignee_and_leader_roles_can_edit_both_active_states(self):
        for status in (Chore.Status.OPEN, Chore.Status.IN_PROGRESS):
            for actor in (self.creator, self.assignee, self.leader):
                with self.subTest(status=status, actor=actor.name):
                    chore = self.make_chore(status=status)
                    before = self.snapshot(chore)
                    self.select_member(actor)
                    self.assertContains(
                        self.client.get(self.detail_url(chore)), self.edit_url(chore)
                    )
                    response = self.client.get(self.edit_url(chore))
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.context["form"].instance.pk, chore.pk)
                    response = self.client.post(
                        self.edit_url(chore),
                        self.chore_data(
                            assignee=str(self.unrelated.pk),
                            creator=str(self.outsider.pk),
                            creator_id=str(self.outsider.pk),
                            status=Chore.Status.COMPLETED,
                            created_at="2000-01-01T01:02:03Z",
                            completed_at="2000-01-02T01:02:03Z",
                        ),
                    )
                    self.assertRedirects(response, self.detail_url(chore))
                    after = self.snapshot(chore)
                    expected = dict(
                        before,
                        title="Wash the dishes",
                        description="Include the pans",
                        assignee_id=self.unrelated.pk,
                        due_date=date(2026, 11, 12),
                    )
                    self.assertEqual(after, expected)

    def test_assign_reassign_and_clear_optional_fields_in_both_active_states(self):
        for status in (Chore.Status.OPEN, Chore.Status.IN_PROGRESS):
            with self.subTest(status=status):
                self.select_member(self.creator)
                chore = self.make_chore(status=status, assignee=None)
                for assignee in (self.assignee, self.unrelated, None):
                    with self.subTest(assignee=assignee):
                        response = self.client.post(
                            self.edit_url(chore),
                            self.chore_data(
                                assignee=str(assignee.pk) if assignee else "",
                                description="",
                                due_date="",
                            ),
                        )
                        self.assertRedirects(response, self.detail_url(chore))
                        chore.refresh_from_db()
                        self.assertEqual(chore.assignee, assignee)
                        self.assertEqual(chore.description, "")
                        self.assertIsNone(chore.due_date)
                        self.assertEqual(chore.status, status)

    def test_old_assignee_loses_edit_permission_after_reassignment_or_unassignment(self):
        for status in (Chore.Status.OPEN, Chore.Status.IN_PROGRESS):
            for replacement in (self.unrelated, None):
                with self.subTest(status=status, replacement=replacement):
                    chore = self.make_chore(status=status)
                    self.select_member(self.creator)
                    response = self.client.post(
                        self.edit_url(chore),
                        self.chore_data(
                            assignee=str(replacement.pk) if replacement else ""
                        ),
                    )
                    self.assertRedirects(response, self.detail_url(chore))
                    self.select_member(self.assignee)
                    self.assert_denied_edit_without_mutation(chore)
                    if replacement:
                        self.select_member(replacement)
                        self.assertEqual(
                            self.client.get(self.edit_url(chore)).status_code, 200
                        )

    def assert_denied_edit_without_mutation(self, chore):
        before = self.snapshot(chore)
        count = Chore.objects.count()
        self.assertNotContains(
            self.client.get(self.detail_url(chore)), self.edit_url(chore)
        )
        for method in ("get", "post"):
            response = getattr(self.client, method)(
                self.edit_url(chore),
                self.chore_data(
                    creator=str(self.leader.pk),
                    status=Chore.Status.OPEN,
                    created_at="2000-01-01T01:02:03Z",
                    completed_at="",
                ),
            )
            self.assertEqual(response.status_code, 403)
            self.assertEqual(self.snapshot(chore), before)
            self.assertEqual(Chore.objects.count(), count)

    def test_unrelated_member_cannot_get_or_submit_edits_in_either_active_state(self):
        self.select_member(self.unrelated)
        for status in (Chore.Status.OPEN, Chore.Status.IN_PROGRESS):
            with self.subTest(status=status):
                self.assert_denied_edit_without_mutation(
                    self.make_chore(status=status)
                )

    def test_completed_normal_fields_are_read_only_for_each_separate_role(self):
        chore = self.make_chore(status=Chore.Status.COMPLETED)
        for actor in (self.creator, self.assignee, self.leader, self.unrelated):
            with self.subTest(actor=actor.name):
                self.select_member(actor)
                self.assert_denied_edit_without_mutation(chore)


class ChoreFormValidationTests(Task4TestCase):
    def test_forms_expose_only_normal_fields_and_active_household_assignees(self):
        chore = self.make_chore()
        for url in (reverse("chores:chore_create"), self.edit_url(chore)):
            with self.subTest(url=url):
                response = self.client.get(url)
                form = response.context["form"]
                self.assertEqual(
                    list(form.fields), ["title", "description", "assignee", "due_date"]
                )
                choices = form.fields["assignee"]
                self.assertQuerySetEqual(
                    choices.queryset,
                    [self.creator, self.assignee, self.unrelated, self.leader],
                    ordered=False,
                )
                self.assertEqual(choices.empty_label, "Unassigned")
                self.assertEqual(list(choices.choices)[0], ("", "Unassigned"))
                self.assertContains(response, ">Unassigned</option>")
                self.assertNotContains(response, self.inactive.name)
                self.assertNotContains(response, self.outsider.name)
                for field in ("creator", "status", "created_at", "completed_at"):
                    self.assertNotContains(response, f'name="{field}"')

    def invalid_payloads(self):
        yield "title", {
            key: value for key, value in self.chore_data().items() if key != "title"
        }
        for title in ("", "   ", "x" * 201):
            yield "title", self.chore_data(title=title)
        yield "due_date", self.chore_data(due_date="2026-02-30")
        yield "due_date", self.chore_data(due_date="not-a-date")
        for assignee in (
            str(uuid4()), "not-a-uuid", str(self.inactive.pk), str(self.outsider.pk)
        ):
            yield "assignee", self.chore_data(assignee=assignee)

    def test_invalid_creation_reports_errors_and_creates_no_record(self):
        for field, payload in self.invalid_payloads():
            with self.subTest(field=field, payload=payload):
                response = self.client.post(reverse("chores:chore_create"), payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.context["form"].errors)
                self.assertContains(response, 'class="errorlist"', status_code=400)
                self.assertEqual(Chore.objects.count(), 0)

    def test_invalid_assignment_and_reassignment_leave_every_stored_field_unchanged(self):
        for status in (Chore.Status.OPEN, Chore.Status.IN_PROGRESS):
            for assignee in (None, self.assignee):
                chore = self.make_chore(status=status, assignee=assignee)
                before = self.snapshot(chore)
                count = Chore.objects.count()
                for field, payload in self.invalid_payloads():
                    with self.subTest(
                        status=status, assignee=assignee, field=field, payload=payload
                    ):
                        response = self.client.post(self.edit_url(chore), payload)
                        self.assertEqual(response.status_code, 400)
                        self.assertIn(field, response.context["form"].errors)
                        self.assertContains(response, 'class="errorlist"', status_code=400)
                        self.assertEqual(self.snapshot(chore), before)
                        self.assertEqual(Chore.objects.count(), count)

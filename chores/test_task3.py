"""Request and domain coverage for Task 3."""

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from chores.current_member import CURRENT_MEMBER_SESSION_KEY
from chores.models import Chore, Household, Member


class Task3TestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.household, cls.leader = Household.objects.create_with_leader(
            household_name="Home",
            leader_name="Alex",
        )
        cls.member = Member.objects.create(
            household=cls.household,
            name="Bailey",
        )
        cls.inactive_member = Member.objects.create(
            household=cls.household,
            name="Casey",
            is_active=False,
        )

    def select_member(self, member):
        session = self.client.session
        session[CURRENT_MEMBER_SESSION_KEY] = str(member.pk)
        session.save()

    def assert_member_unchanged(self, member, *, name, is_active):
        member.refresh_from_db()
        self.assertEqual(member.name, name)
        self.assertEqual(member.is_active, is_active)


class CurrentMemberTests(Task3TestCase):
    def test_selector_contains_only_active_household_members(self):
        response = self.client.get(reverse("chores:home"))

        choices = response.context["current_member_form"].fields[
            "member"
        ].queryset
        self.assertQuerySetEqual(
            choices,
            [self.leader, self.member],
            ordered=False,
        )
        self.assertContains(response, self.leader.name)
        self.assertContains(response, self.member.name)
        self.assertNotContains(response, self.inactive_member.name)

    def test_selecting_member_persists_for_subsequent_requests(self):
        response = self.client.post(
            reverse("chores:set_current_member"),
            {"member": self.member.pk},
        )

        self.assertRedirects(response, reverse("chores:home"))
        self.assertEqual(
            self.client.session[CURRENT_MEMBER_SESSION_KEY],
            str(self.member.pk),
        )

        response = self.client.get(reverse("chores:home"))
        self.assertEqual(response.context["current_member"], self.member)
        self.assertContains(response, "Acting as:")
        self.assertContains(response, self.member.name)

    def test_selection_does_not_modify_member_record(self):
        original_name = self.member.name
        original_is_active = self.member.is_active

        self.client.post(
            reverse("chores:set_current_member"),
            {"member": self.member.pk},
        )

        self.assert_member_unchanged(
            self.member,
            name=original_name,
            is_active=original_is_active,
        )

    def test_inactive_member_cannot_be_selected_by_crafted_request(self):
        response = self.client.post(
            reverse("chores:set_current_member"),
            {"member": self.inactive_member.pk},
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response,
            "Select a valid choice",
            status_code=400,
        )
        self.assertNotIn(CURRENT_MEMBER_SESSION_KEY, self.client.session)

    def test_stale_inactive_session_selection_is_cleared(self):
        self.select_member(self.inactive_member)

        response = self.client.get(reverse("chores:home"))

        self.assertIsNone(response.context["current_member"])
        self.assertNotIn(CURRENT_MEMBER_SESSION_KEY, self.client.session)
        self.assertContains(response, "Choose an active Current Member")

    def test_missing_session_member_is_cleared(self):
        session = self.client.session
        session[CURRENT_MEMBER_SESSION_KEY] = "00000000-0000-0000-0000-000000000000"
        session.save()

        response = self.client.get(reverse("chores:home"))

        self.assertIsNone(response.context["current_member"])
        self.assertNotIn(CURRENT_MEMBER_SESSION_KEY, self.client.session)


class MemberManagementPermissionTests(Task3TestCase):
    def test_leader_can_access_member_management(self):
        self.select_member(self.leader)

        response = self.client.get(reverse("chores:member_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manage members")

    def test_regular_member_cannot_access_member_management(self):
        self.select_member(self.member)

        response = self.client.get(reverse("chores:member_list"))

        self.assertEqual(response.status_code, 403)

    def test_regular_member_cannot_add_members(self):
        self.select_member(self.member)

        response = self.client.post(
            reverse("chores:member_add"),
            {"name": "Drew"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Member.objects.filter(name="Drew").exists())

    def test_regular_member_cannot_rename_members(self):
        self.select_member(self.member)

        response = self.client.post(
            reverse("chores:member_rename", args=[self.member.pk]),
            {"name": "Changed"},
        )

        self.assertEqual(response.status_code, 403)
        self.assert_member_unchanged(
            self.member,
            name="Bailey",
            is_active=True,
        )

    def test_regular_member_cannot_deactivate_members(self):
        self.select_member(self.member)

        response = self.client.post(
            reverse("chores:member_deactivate", args=[self.member.pk]),
        )

        self.assertEqual(response.status_code, 403)
        self.assert_member_unchanged(
            self.member,
            name="Bailey",
            is_active=True,
        )


class MemberManagementTests(Task3TestCase):
    def setUp(self):
        self.select_member(self.leader)

    def test_leader_can_add_regular_member(self):
        response = self.client.post(
            reverse("chores:member_add"),
            {"name": "Drew"},
        )

        self.assertRedirects(response, reverse("chores:member_list"))
        added = Member.objects.get(name="Drew")
        self.assertEqual(added.household, self.household)
        self.assertTrue(added.is_active)
        self.assertFalse(added.is_leader)

    def test_leader_can_rename_regular_member(self):
        response = self.client.post(
            reverse("chores:member_rename", args=[self.member.pk]),
            {"name": "Bailey Renamed"},
        )

        self.assertRedirects(response, reverse("chores:member_list"))
        self.assert_member_unchanged(
            self.member,
            name="Bailey Renamed",
            is_active=True,
        )

    def test_leader_can_rename_the_leader(self):
        response = self.client.post(
            reverse("chores:member_rename", args=[self.leader.pk]),
            {"name": "Alex Renamed"},
        )

        self.assertRedirects(response, reverse("chores:member_list"))
        self.assert_member_unchanged(
            self.leader,
            name="Alex Renamed",
            is_active=True,
        )

    def test_member_removal_is_deactivation_not_deletion(self):
        member_id = self.member.pk

        response = self.client.post(
            reverse("chores:member_deactivate", args=[member_id]),
        )

        self.assertRedirects(response, reverse("chores:member_list"))
        self.assertTrue(Member.objects.filter(pk=member_id).exists())
        self.assert_member_unchanged(
            self.member,
            name="Bailey",
            is_active=False,
        )

        response = self.client.get(reverse("chores:home"))
        choices = response.context["current_member_form"].fields[
            "member"
        ].queryset
        self.assertNotIn(self.member, choices)

    def test_leader_cannot_be_deactivated(self):
        response = self.client.post(
            reverse("chores:member_deactivate", args=[self.leader.pk]),
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response,
            "household leader must remain active",
            status_code=400,
        )
        self.assert_member_unchanged(
            self.leader,
            name="Alex",
            is_active=True,
        )

    def test_inactive_member_remains_visible_to_leader(self):
        response = self.client.get(reverse("chores:member_list"))

        self.assertContains(response, self.inactive_member.name)
        self.assertContains(response, "(Inactive)")


class DeactivationGuardTests(Task3TestCase):
    def setUp(self):
        self.select_member(self.leader)

    def make_assigned_chore(self, status):
        return Chore.objects.create(
            title=f"A {status} chore",
            creator=self.leader,
            assignee=self.member,
            status=status,
        )

    def test_open_assigned_chore_blocks_deactivation(self):
        self.make_assigned_chore(Chore.Status.OPEN)

        response = self.client.post(
            reverse("chores:member_deactivate", args=[self.member.pk]),
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response,
            "assigned non-completed chores cannot be deactivated",
            status_code=400,
        )
        self.assert_member_unchanged(
            self.member,
            name="Bailey",
            is_active=True,
        )

    def test_in_progress_assigned_chore_blocks_deactivation(self):
        self.make_assigned_chore(Chore.Status.IN_PROGRESS)

        response = self.client.post(
            reverse("chores:member_deactivate", args=[self.member.pk]),
        )

        self.assertEqual(response.status_code, 400)
        self.assert_member_unchanged(
            self.member,
            name="Bailey",
            is_active=True,
        )

    def test_completed_assigned_chore_does_not_block_deactivation(self):
        chore = self.make_assigned_chore(Chore.Status.COMPLETED)

        response = self.client.post(
            reverse("chores:member_deactivate", args=[self.member.pk]),
        )

        self.assertRedirects(response, reverse("chores:member_list"))
        self.assert_member_unchanged(
            self.member,
            name="Bailey",
            is_active=False,
        )
        chore.refresh_from_db()
        self.assertEqual(chore.assignee, self.member)
        self.assertEqual(chore.creator, self.leader)
        self.assertEqual(chore.status, Chore.Status.COMPLETED)
        self.assertIsNotNone(chore.completed_at)

    def test_rejected_deactivation_does_not_mutate_member_or_chore(self):
        chore = self.make_assigned_chore(Chore.Status.IN_PROGRESS)
        original_chore = {
            "title": chore.title,
            "creator_id": chore.creator_id,
            "assignee_id": chore.assignee_id,
            "status": chore.status,
            "completed_at": chore.completed_at,
        }

        self.client.post(
            reverse("chores:member_deactivate", args=[self.member.pk]),
        )

        self.assert_member_unchanged(
            self.member,
            name="Bailey",
            is_active=True,
        )
        chore.refresh_from_db()
        self.assertEqual(chore.title, original_chore["title"])
        self.assertEqual(chore.creator_id, original_chore["creator_id"])
        self.assertEqual(chore.assignee_id, original_chore["assignee_id"])
        self.assertEqual(chore.status, original_chore["status"])
        self.assertEqual(chore.completed_at, original_chore["completed_at"])

    def test_model_save_also_rejects_deactivation_with_active_assignment(self):
        chore = self.make_assigned_chore(Chore.Status.OPEN)
        self.member.is_active = False

        with self.assertRaises(ValidationError):
            self.member.save(update_fields={"is_active"})

        self.member.refresh_from_db()
        chore.refresh_from_db()
        self.assertTrue(self.member.is_active)
        self.assertEqual(chore.assignee, self.member)
        self.assertEqual(chore.status, Chore.Status.OPEN)

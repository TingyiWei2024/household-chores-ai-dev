from datetime import timedelta
from io import StringIO

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from chores.models import Chore, Household, Member


class ChoresAppSmokeTest(SimpleTestCase):
    def test_app_is_registered(self):
        self.assertEqual(apps.get_app_config("chores").name, "chores")


class HouseholdAndMemberModelTests(TestCase):
    def test_household_contains_one_leader_and_regular_members(self):
        household, leader = Household.objects.create_with_leader(
            household_name="Home",
            leader_name="Alex",
        )
        regular_member = Member.objects.create(
            household=household,
            name="Bailey",
        )

        self.assertEqual(household.leader, leader)
        self.assertEqual(
            list(household.members.order_by("name")),
            [leader, regular_member],
        )
        self.assertTrue(leader.is_leader)
        self.assertFalse(regular_member.is_leader)
        self.assertTrue(leader.is_active)
        self.assertTrue(regular_member.is_active)
        self.assertEqual(
            sum(member.is_leader for member in household.members.all()),
            1,
        )

    def test_household_cannot_be_saved_without_a_leader(self):
        with self.assertRaises(ValidationError):
            Household.objects.create(name="Leaderless Home")

    def test_household_rejects_a_leader_from_another_household(self):
        household, original_leader = Household.objects.create_with_leader(
            household_name="Home",
            leader_name="Alex",
        )
        _, other_leader = Household.objects.create_with_leader(
            household_name="Other Home",
            leader_name="Casey",
        )

        household.leader = other_leader
        with self.assertRaises(ValidationError):
            household.save()

        household.refresh_from_db()
        self.assertEqual(household.leader, original_leader)

    def test_household_rejects_an_inactive_member_as_leader(self):
        household, original_leader = Household.objects.create_with_leader(
            household_name="Home",
            leader_name="Alex",
        )
        inactive_member = Member.objects.create(
            household=household,
            name="Bailey",
            is_active=False,
        )

        household.leader = inactive_member
        with self.assertRaises(ValidationError):
            household.save()

        household.refresh_from_db()
        self.assertEqual(household.leader, original_leader)

    def test_household_can_replace_its_leader_without_having_zero_or_two(self):
        household, original_leader = Household.objects.create_with_leader(
            household_name="Home",
            leader_name="Alex",
        )
        new_leader = Member.objects.create(household=household, name="Bailey")

        household.leader = new_leader
        household.save()

        original_leader.refresh_from_db()
        new_leader.refresh_from_db()
        self.assertFalse(original_leader.is_leader)
        self.assertTrue(new_leader.is_leader)
        self.assertEqual(
            sum(member.is_leader for member in household.members.all()),
            1,
        )

    def test_leader_cannot_be_deleted_or_made_inactive(self):
        household, leader = Household.objects.create_with_leader(
            household_name="Home",
            leader_name="Alex",
        )

        with self.assertRaises(ProtectedError):
            leader.delete()

        leader.is_active = False
        with self.assertRaises(ValidationError):
            leader.save()

        household.refresh_from_db()
        leader.refresh_from_db()
        self.assertEqual(household.leader, leader)
        self.assertTrue(leader.is_active)

    def test_regular_member_can_be_stored_as_inactive(self):
        household, _ = Household.objects.create_with_leader(
            household_name="Home",
            leader_name="Alex",
        )

        member = Member.objects.create(
            household=household,
            name="Bailey",
            is_active=False,
        )

        self.assertFalse(member.is_active)
        self.assertFalse(member.is_leader)


class ChoreModelTests(TestCase):
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

    def test_required_and_defaulted_fields(self):
        chore = Chore.objects.create(
            title="Wash dishes",
            creator=self.leader,
        )

        self.assertEqual(chore.title, "Wash dishes")
        self.assertEqual(chore.creator, self.leader)
        self.assertEqual(chore.description, "")
        self.assertIsNone(chore.assignee)
        self.assertIsNone(chore.due_date)
        self.assertEqual(chore.status, Chore.Status.OPEN)
        self.assertIsNotNone(chore.created_at)
        self.assertIsNone(chore.completed_at)
        self.assertIn(chore, self.leader.created_chores.all())

    def test_title_and_creator_are_required(self):
        with self.assertRaises(ValidationError):
            Chore.objects.create(creator=self.leader)

        with self.assertRaises(ValidationError):
            Chore.objects.create(title="Wash dishes")

    def test_optional_fields_are_stored(self):
        due_date = timezone.localdate() + timedelta(days=2)

        chore = Chore.objects.create(
            title="Wash dishes",
            description="Use the gentle detergent.",
            creator=self.leader,
            assignee=self.member,
            due_date=due_date,
        )

        self.assertEqual(chore.description, "Use the gentle detergent.")
        self.assertEqual(chore.assignee, self.member)
        self.assertEqual(chore.due_date, due_date)
        self.assertIn(chore, self.member.assigned_chores.all())

    def test_status_choices_are_exactly_the_approved_values(self):
        self.assertEqual(
            list(Chore.Status.choices),
            [
                ("open", "Open"),
                ("in_progress", "In Progress"),
                ("completed", "Completed"),
            ],
        )

        for status in Chore.Status.values:
            with self.subTest(status=status):
                chore = Chore.objects.create(
                    title=f"Chore in {status}",
                    creator=self.leader,
                    status=status,
                )
                self.assertEqual(chore.status, status)

    def test_invalid_status_is_rejected_by_model_and_database(self):
        chore = Chore.objects.create(title="Wash dishes", creator=self.leader)
        chore.status = "cancelled"

        with self.assertRaises(ValidationError):
            chore.save()

        with self.assertRaises(IntegrityError), transaction.atomic():
            Chore.objects.filter(pk=chore.pk).update(status="cancelled")

    def test_completed_at_is_set_on_completion_and_cleared_when_not_completed(self):
        chore = Chore.objects.create(title="Wash dishes", creator=self.leader)
        before_completion = timezone.now()

        chore.status = Chore.Status.COMPLETED
        chore.save(update_fields={"status"})
        first_completed_at = chore.completed_at

        self.assertIsNotNone(first_completed_at)
        self.assertGreaterEqual(first_completed_at, before_completion)

        chore.save()
        self.assertEqual(chore.completed_at, first_completed_at)

        chore.status = Chore.Status.IN_PROGRESS
        chore.save(update_fields={"status"})
        chore.refresh_from_db()
        self.assertIsNone(chore.completed_at)

    def test_database_rejects_completion_timestamp_for_non_completed_chore(self):
        chore = Chore.objects.create(title="Wash dishes", creator=self.leader)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Chore.objects.filter(pk=chore.pk).update(completed_at=timezone.now())

    def test_overdue_is_derived_with_strict_due_date_boundary(self):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)

        overdue = Chore.objects.create(
            title="Past due",
            creator=self.leader,
            due_date=yesterday,
        )
        due_today = Chore.objects.create(
            title="Due today",
            creator=self.leader,
            due_date=today,
        )
        future = Chore.objects.create(
            title="Due later",
            creator=self.leader,
            due_date=tomorrow,
        )
        no_due_date = Chore.objects.create(
            title="No due date",
            creator=self.leader,
        )
        completed_past_due = Chore.objects.create(
            title="Completed past due",
            creator=self.leader,
            due_date=yesterday,
            status=Chore.Status.COMPLETED,
        )

        self.assertTrue(overdue.is_overdue)
        self.assertFalse(due_today.is_overdue)
        self.assertFalse(future.is_overdue)
        self.assertFalse(no_due_date.is_overdue)
        self.assertFalse(completed_past_due.is_overdue)


class BootstrapHouseholdCommandTests(TestCase):
    def test_bootstrap_creates_initial_household_and_leader_from_clean_database(self):
        output = StringIO()

        call_command(
            "bootstrap_household",
            household_name="My Home",
            leader_name="Alex",
            stdout=output,
        )

        household = Household.objects.get()
        leader = Member.objects.get()
        self.assertEqual(household.name, "My Home")
        self.assertEqual(household.leader, leader)
        self.assertEqual(leader.name, "Alex")
        self.assertEqual(leader.household, household)
        self.assertTrue(leader.is_active)
        self.assertTrue(leader.is_leader)
        self.assertIn(
            'Created household "My Home" with leader "Alex".',
            output.getvalue(),
        )

    def test_bootstrap_does_not_duplicate_an_existing_household(self):
        call_command(
            "bootstrap_household",
            household_name="My Home",
            leader_name="Alex",
            stdout=StringIO(),
        )

        call_command(
            "bootstrap_household",
            household_name="Another Home",
            leader_name="Bailey",
            stdout=StringIO(),
        )

        self.assertEqual(Household.objects.count(), 1)
        self.assertEqual(Member.objects.count(), 1)
        self.assertEqual(Household.objects.get().name, "My Home")

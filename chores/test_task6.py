"""Date-controlled active-board, member-filter, and household-indicator tests."""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from django.urls import reverse

from chores.board import household_indicators
from chores.current_member import CURRENT_MEMBER_SESSION_KEY
from chores.models import Chore, Household, Member
from chores.test_task4 import Task4TestCase


class Task6TestCase(Task4TestCase):
    def setUp(self):
        super().setUp()
        self.today = date(2026, 9, 9)
        date_patch = patch("chores.board.timezone.localdate", return_value=self.today)
        date_patch.start()
        self.addCleanup(date_patch.stop)

    def board(self, member=None, **extra):
        params = dict(extra)
        if member is not None:
            params["member"] = str(member.pk)
        return self.client.get(reverse("chores:home"), params)

    def assert_rows(self, response, expected, status_code=200):
        self.assertEqual(response.status_code, status_code)
        self.assertEqual(
            {chore.pk for chore in response.context["chores"]},
            {chore.pk for chore in expected},
        )
        for chore in expected:
            self.assertContains(response, self.detail_url(chore), status_code=status_code)

    def stored_data(self):
        return (
            list(Chore.objects.order_by("pk").values()),
            list(Member.objects.order_by("pk").values()),
            list(Household.objects.order_by("pk").values()),
        )


class SharedBoardAndFilterTests(Task6TestCase):
    def test_every_acting_member_sees_all_household_active_chores(self):
        opened = self.make_chore(title="Open assigned", due_date=None)
        progressing = self.make_chore(
            title="Progress unassigned", status=Chore.Status.IN_PROGRESS, assignee=None
        )
        completed = self.make_chore(title="Finished household", status=Chore.Status.COMPLETED)
        outside = self.make_chore(title="Private other home", creator=self.outsider)
        before = self.stored_data()
        for actor in (self.creator, self.assignee, self.leader, self.unrelated):
            with self.subTest(actor=actor.name):
                self.select_member(actor)
                response = self.board()
                self.assert_rows(response, [opened, progressing])
                self.assertContains(response, reverse("chores:chore_create"))
                self.assertNotContains(response, completed.title)
                self.assertNotContains(response, outside.title)
                self.assertEqual(response.context["current_member"], actor)
        self.assertEqual(self.stored_data(), before)
        self.assertEqual(self.client.get(self.detail_url(completed)).status_code, 200)

    def test_member_filter_uses_assignee_and_reset_restores_unassigned(self):
        assigned = self.make_chore(creator=self.unrelated, assignee=self.creator)
        created_only = self.make_chore(creator=self.creator, assignee=self.assignee)
        unassigned = self.make_chore(assignee=None)
        self.make_chore(assignee=self.creator, status=Chore.Status.COMPLETED)
        before = self.stored_data()
        self.assert_rows(self.board(self.creator), [assigned])
        self.assert_rows(self.board(self.assignee), [created_only])
        self.assert_rows(self.board(), [assigned, created_only, unassigned])
        self.assert_rows(self.client.get(reverse("chores:home"), {"member": ""}),
                         [assigned, created_only, unassigned])
        self.assertEqual(self.stored_data(), before)
        self.assertEqual(self.client.session[CURRENT_MEMBER_SESSION_KEY], str(self.creator.pk))

    def test_filter_includes_household_members_without_changing_acting_or_assignment_choices(self):
        response = self.board(self.inactive)
        choices = response.context["board_filter"].fields["member"].queryset
        self.assertQuerySetEqual(choices, self.household.members.all(), ordered=False)
        self.assertNotIn(self.outsider, choices)
        self.assertNotIn(
            self.inactive, response.context["current_member_form"].fields["member"].queryset
        )
        self.assertContains(response, "Filter by member")
        self.assertContains(response, 'id="id_filter_member"')
        self.assertContains(response, 'id="id_member"')
        self.assertEqual(response.context["current_member"], self.creator)
        self.assertNotIn(
            self.inactive,
            self.client.get(reverse("chores:chore_create")).context["form"].fields["assignee"].queryset,
        )

    def test_empty_board_and_empty_filter_keep_indicators_visible(self):
        for response in (self.board(), self.board(self.unrelated)):
            self.assert_rows(response, [])
            self.assertContains(response, "No active chores match this view.")
            self.assertContains(response, "This Week Completion Rate")
            self.assertContains(response, "Overdue Chores Count")
            self.assertContains(response, "No chores due this week")
            self.assertEqual(response.context["indicators"]["overdue_count"], 0)

    def test_invalid_filters_show_errors_without_data_or_identity_changes(self):
        self.make_chore(due_date=self.today)
        outside = self.make_chore(
            creator=self.outsider, title="Outside private title", due_date=self.today - timedelta(days=1)
        )
        before = self.stored_data()
        for value in ("not-a-uuid", str(uuid4()), str(self.outsider.pk)):
            with self.subTest(value=value):
                response = self.client.get(reverse("chores:home"), {"member": value})
                self.assert_rows(response, [], status_code=400)
                self.assertIn("member", response.context["board_filter"].errors)
                self.assertContains(response, 'class="errorlist"', status_code=400)
                self.assertNotContains(response, outside.title, status_code=400)
                self.assertEqual(response.context["indicators"]["week_total"], 1)
                self.assertEqual(response.context["indicators"]["overdue_count"], 0)
                self.assertEqual(response.context["current_member"], self.creator)
                self.assertEqual(self.client.session[CURRENT_MEMBER_SESSION_KEY], str(self.creator.pk))
                self.assertEqual(self.stored_data(), before)

    def test_missing_and_stale_selections_keep_prompt_and_hide_board_data(self):
        chore = self.make_chore(title="Hidden until selection")
        before = self.stored_data()
        for value in (None, str(uuid4()), str(self.inactive.pk), str(self.outsider.pk), "bad-id"):
            with self.subTest(value=value):
                session = self.client.session
                session.pop(CURRENT_MEMBER_SESSION_KEY, None)
                if value is not None:
                    session[CURRENT_MEMBER_SESSION_KEY] = value
                session.save()
                response = self.board(self.creator)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Choose an active Current Member")
                self.assertNotContains(response, chore.title)
                self.assertNotIn(CURRENT_MEMBER_SESSION_KEY, self.client.session)
                self.assertEqual(self.stored_data(), before)

    def test_uninitialized_household_still_has_its_existing_page(self):
        with patch("chores.middleware.get_single_household", return_value=None):
            response = self.board()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The household has not been initialized yet.")

    def test_board_query_parameters_cannot_trigger_workflow_or_normal_edits(self):
        chore = self.make_chore(assignee=None)
        before = self.stored_data()
        response = self.board(action="claim", status="completed", title="Injected")
        self.assert_rows(response, [chore])
        self.assertEqual(self.stored_data(), before)
        response = self.client.post(reverse("chores:home"), {"action": "claim"})
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.stored_data(), before)


class IndicatorAndDateTests(Task6TestCase):
    def test_overdue_rows_and_count_use_strict_date_and_noncompleted_status(self):
        old = self.make_chore(title="Long overdue", due_date=date(2020, 1, 1), assignee=None)
        yesterday = self.make_chore(
            title="Yesterday", status=Chore.Status.IN_PROGRESS,
            due_date=self.today - timedelta(days=1),
        )
        today = self.make_chore(title="Today", due_date=self.today)
        future = self.make_chore(title="Future", due_date=self.today + timedelta(days=1))
        undated = self.make_chore(title="Undated", due_date=None)
        self.make_chore(status=Chore.Status.COMPLETED, due_date=date(2020, 1, 1))
        self.make_chore(creator=self.outsider, due_date=date(2020, 1, 1))
        before = self.stored_data()
        response = self.board()
        self.assert_rows(response, [old, yesterday, today, future, undated])
        self.assertContains(response, "<strong>Overdue</strong>", count=2, html=True)
        self.assertEqual(response.context["indicators"]["overdue_count"], 2)
        self.assertTrue(old.is_overdue)
        self.assertTrue(yesterday.is_overdue)
        for chore in (today, future, undated):
            self.assertFalse(chore.is_overdue)
        self.assertEqual(self.stored_data(), before)

    def test_monday_sunday_and_month_year_crossover_boundaries(self):
        for today, monday, sunday in (
            (date(2026, 9, 7), date(2026, 9, 7), date(2026, 9, 13)),
            (date(2026, 9, 13), date(2026, 9, 7), date(2026, 9, 13)),
            (date(2026, 8, 31), date(2026, 8, 31), date(2026, 9, 6)),
            (date(2025, 12, 29), date(2025, 12, 29), date(2026, 1, 4)),
            (date(2026, 1, 4), date(2025, 12, 29), date(2026, 1, 4)),
        ):
            with self.subTest(today=today):
                Chore.objects.all().delete()
                self.make_chore(due_date=monday, status=Chore.Status.COMPLETED)
                self.make_chore(due_date=sunday, assignee=None)
                self.make_chore(due_date=monday - timedelta(days=1), status=Chore.Status.COMPLETED)
                self.make_chore(due_date=sunday + timedelta(days=1), status=Chore.Status.IN_PROGRESS)
                self.make_chore(due_date=None, status=Chore.Status.COMPLETED)
                with patch("chores.board.timezone.localdate", return_value=today):
                    response = self.board()
                metrics = response.context["indicators"]
                self.assertEqual(metrics["week_start"], monday)
                self.assertEqual(metrics["week_end"], sunday)
                self.assertEqual(metrics["week_total"], 2)
                self.assertEqual(metrics["week_completed"], 1)
                self.assertEqual(metrics["completion_rate"], 50)
                self.assertContains(response, "50%")

    def test_weekly_ratio_includes_all_statuses_and_ignores_record_timestamps(self):
        completed = self.make_chore(status=Chore.Status.COMPLETED, due_date=self.today)
        self.make_chore(status=Chore.Status.OPEN, due_date=self.today, assignee=None)
        self.make_chore(status=Chore.Status.IN_PROGRESS, due_date=self.today)
        self.make_chore(status=Chore.Status.COMPLETED, due_date=None)
        self.make_chore(status=Chore.Status.COMPLETED, due_date=date(2020, 1, 1))
        self.make_chore(creator=self.outsider, status=Chore.Status.COMPLETED, due_date=self.today)
        Chore.objects.filter(pk=completed.pk).update(
            created_at=datetime(2000, 1, 1, tzinfo=UTC),
            completed_at=datetime(2030, 1, 1, tzinfo=UTC),
        )
        metrics = household_indicators(self.household)
        self.assertEqual(metrics["week_total"], 3)
        self.assertEqual(metrics["week_completed"], 1)
        self.assertAlmostEqual(metrics["completion_rate"], 100 / 3)
        self.assertContains(self.board(), "33.3%")

    def test_no_eligible_chores_has_exact_message_instead_of_zero_percentage(self):
        undated = self.make_chore(due_date=None)
        self.make_chore(status=Chore.Status.COMPLETED, due_date=date(2020, 1, 1))
        response = self.board()
        self.assert_rows(response, [undated])
        self.assertContains(response, "<p>No chores due this week</p>", html=True)
        self.assertNotContains(response, "%")
        self.assertEqual(response.context["indicators"]["week_total"], 0)
        self.assertIsNone(response.context["indicators"]["completion_rate"])

    def test_zero_and_all_completed_rates_are_distinct_from_no_eligible_work(self):
        chore = self.make_chore(due_date=self.today, status=Chore.Status.IN_PROGRESS)
        response = self.board()
        self.assertContains(response, "<strong>0%</strong>", html=True)
        self.assertNotContains(response, "No chores due this week")
        self.select_member(self.leader)
        self.assertEqual(
            self.client.post(reverse("chores:chore_action", args=[chore.pk]),
                             {"action": "complete"}).status_code, 302
        )
        response = self.board()
        self.assert_rows(response, [])
        self.assertContains(response, "No active chores match this view.")
        self.assertContains(response, "<strong>100%</strong>", html=True)
        self.assertEqual(response.context["indicators"]["week_total"], 1)
        self.assertEqual(response.context["indicators"]["week_completed"], 1)

    def test_household_indicators_do_not_follow_member_filter_or_acting_identity(self):
        mine = self.make_chore(assignee=self.creator, due_date=self.today - timedelta(days=1))
        theirs = self.make_chore(assignee=self.assignee, due_date=self.today)
        unassigned = self.make_chore(assignee=None, due_date=date(2020, 1, 1))
        self.make_chore(assignee=self.assignee, status=Chore.Status.COMPLETED, due_date=self.today)
        expected = household_indicators(self.household)
        self.assertEqual((expected["week_total"], expected["week_completed"], expected["overdue_count"]),
                         (3, 1, 2))
        before = self.stored_data()
        for actor in (self.creator, self.assignee, self.leader):
            self.select_member(actor)
            for member, rows in ((self.creator, [mine]), (self.assignee, [theirs]),
                                 (self.unrelated, []), (None, [mine, theirs, unassigned])):
                with self.subTest(actor=actor.name, member=member):
                    response = self.board(member)
                    self.assert_rows(response, rows)
                    self.assertEqual(response.context["indicators"], expected)
                    self.assertEqual(response.context["current_member"], actor)
        self.assertEqual(self.stored_data(), before)


class BoardWorkflowIntegrationTests(Task6TestCase):
    def test_completion_and_undo_update_board_and_both_indicators(self):
        chore = self.make_chore(status=Chore.Status.IN_PROGRESS,
                                due_date=self.today - timedelta(days=1))
        self.select_member(self.assignee)
        response = self.board()
        self.assert_rows(response, [chore])
        self.assertEqual(response.context["indicators"]["overdue_count"], 1)
        self.assertEqual(response.context["indicators"]["completion_rate"], 0)
        for action, rows, rate, overdue in (
            ("complete", [], 100, 0),
            ("undo_completion", [chore], 0, 1),
        ):
            with self.subTest(action=action):
                response = self.client.post(
                    reverse("chores:chore_action", args=[chore.pk]), {"action": action}
                )
                self.assertRedirects(response, self.detail_url(chore))
                response = self.board()
                self.assert_rows(response, rows)
                self.assertEqual(response.context["indicators"]["week_total"], 1)
                self.assertEqual(response.context["indicators"]["completion_rate"], rate)
                self.assertEqual(response.context["indicators"]["overdue_count"], overdue)
        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.Status.IN_PROGRESS)

    def test_assignment_reassignment_and_unassignment_change_rows_not_indicators(self):
        chore = self.make_chore(assignee=None, due_date=self.today - timedelta(days=1))
        expected = household_indicators(self.household)
        for assignee in (self.assignee, self.unrelated, None):
            with self.subTest(assignee=assignee):
                response = self.client.post(
                    self.edit_url(chore),
                    self.chore_data(assignee=str(assignee.pk) if assignee else "",
                                    due_date=chore.due_date.isoformat()),
                )
                self.assertRedirects(response, self.detail_url(chore))
                for member in (self.assignee, self.unrelated):
                    response = self.board(member)
                    self.assert_rows(response, [chore] if member == assignee else [])
                    self.assertEqual(response.context["indicators"], expected)
                self.assert_rows(self.board(), [chore])

    def test_inactive_historical_assignee_remains_filterable_after_leader_undo(self):
        chore = self.make_chore(status=Chore.Status.COMPLETED, due_date=self.today)
        self.select_member(self.leader)
        self.assertEqual(self.client.post(
            reverse("chores:member_deactivate", args=[self.assignee.pk])
        ).status_code, 302)
        self.assertEqual(self.client.post(
            reverse("chores:chore_action", args=[chore.pk]), {"action": "undo_completion"}
        ).status_code, 302)
        response = self.board(self.assignee)
        self.assert_rows(response, [chore])
        self.assertContains(response, self.assignee.name)
        self.assertEqual(response.context["current_member"], self.leader)

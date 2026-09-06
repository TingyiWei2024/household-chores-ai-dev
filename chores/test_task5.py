"""Request and domain coverage for explicit chore workflow actions."""

from datetime import UTC, datetime
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models.query import QuerySet
from django.test import Client
from django.urls import reverse

from chores.actions import perform_chore_action
from chores.current_member import CURRENT_MEMBER_SESSION_KEY
from chores.models import Chore, Member
from chores.test_task4 import Task4TestCase


class Task5TestCase(Task4TestCase):
    def action_url(self, chore):
        return reverse("chores:chore_action", args=[chore.pk])

    def act(self, chore, action, **extra):
        return self.client.post(self.action_url(chore), {"action": action, **extra})

    def assert_unchanged(self, chore, before, count):
        self.assertEqual(self.snapshot(chore), before)
        self.assertEqual(Chore.objects.count(), count)

    def assert_success(self, response, chore, before, **changes):
        self.assertRedirects(response, self.detail_url(chore))
        self.assertEqual(self.snapshot(chore), dict(before, **changes))


class ClaimRequestTests(Task5TestCase):
    def test_creator_other_regular_member_and_leader_can_claim(self):
        for actor in (self.creator, self.unrelated, self.leader):
            with self.subTest(actor=actor.name):
                chore = self.make_chore(assignee=None)
                before = self.snapshot(chore)
                self.select_member(actor)
                response = self.act(chore, "claim")
                self.assert_success(response, chore, before, assignee_id=actor.pk)
                detail = self.client.get(self.detail_url(chore))
                self.assertContains(detail, actor.name)
                self.assertContains(detail, "Open")

    def test_assigned_in_progress_and_completed_claims_are_rejected(self):
        for status in Chore.Status.values:
            for assignee in (None, self.assignee):
                if status == Chore.Status.OPEN and assignee is None:
                    continue
                chore = self.make_chore(status=status, assignee=assignee)
                before, count = self.snapshot(chore), Chore.objects.count()
                for actor in (self.assignee, self.unrelated, self.leader):
                    with self.subTest(status=status, assignee=assignee, actor=actor.name):
                        self.select_member(actor)
                        self.assertEqual(self.act(chore, "claim").status_code, 400)
                        self.assert_unchanged(chore, before, count)

    def test_stale_claim_form_cannot_replace_first_claimant(self):
        chore = self.make_chore(assignee=None)
        self.select_member(self.unrelated)
        stale_detail = self.client.get(self.detail_url(chore))
        self.assertContains(stale_detail, 'value="claim"')
        self.select_member(self.creator)
        self.assertEqual(self.act(chore, "claim").status_code, 302)
        winner, count = self.snapshot(chore), Chore.objects.count()
        self.select_member(self.unrelated)
        self.assertEqual(self.act(chore, "claim").status_code, 400)
        self.assert_unchanged(chore, winner, count)


class WorkflowRequestTests(Task5TestCase):
    def test_separate_assignee_and_leader_roles_perform_forward_actions(self):
        for actor, assignee in (
            (self.assignee, self.assignee),
            (self.leader, self.assignee),
            (self.leader, None),
        ):
            for action, source, target in (
                ("start", Chore.Status.OPEN, Chore.Status.IN_PROGRESS),
                ("complete", Chore.Status.IN_PROGRESS, Chore.Status.COMPLETED),
            ):
                with self.subTest(actor=actor.name, assignee=assignee, action=action):
                    chore = self.make_chore(status=source, assignee=assignee)
                    before = self.snapshot(chore)
                    self.select_member(actor)
                    completed_at = datetime(2026, 9, 7, 12, 30, tzinfo=UTC)
                    with patch("chores.actions.timezone.now", return_value=completed_at):
                        response = self.act(chore, action)
                    self.assert_success(
                        response, chore, before, status=target,
                        completed_at=completed_at if action == "complete" else None,
                    )

    def test_creator_only_and_unrelated_members_cannot_change_workflow(self):
        for actor in (self.creator, self.unrelated):
            for action, status in (
                ("start", Chore.Status.OPEN),
                ("complete", Chore.Status.IN_PROGRESS),
                ("undo_completion", Chore.Status.COMPLETED),
            ):
                with self.subTest(actor=actor.name, action=action):
                    chore = self.make_chore(status=status)
                    before, count = self.snapshot(chore), Chore.objects.count()
                    self.select_member(actor)
                    self.assertEqual(self.act(chore, action).status_code, 403)
                    self.assert_unchanged(chore, before, count)

    def test_old_assignee_cannot_start_or_complete_after_reassignment_or_unassignment(self):
        for action, status in (
            ("start", Chore.Status.OPEN),
            ("complete", Chore.Status.IN_PROGRESS),
        ):
            for replacement in (self.unrelated, None):
                with self.subTest(action=action, replacement=replacement):
                    chore = self.make_chore(status=status)
                    self.select_member(self.creator)
                    response = self.client.post(
                        self.edit_url(chore),
                        self.chore_data(assignee=str(replacement.pk) if replacement else ""),
                    )
                    self.assertRedirects(response, self.detail_url(chore))
                    before, count = self.snapshot(chore), Chore.objects.count()
                    self.select_member(self.assignee)
                    self.assertEqual(self.act(chore, action).status_code, 403)
                    self.assert_unchanged(chore, before, count)

    def test_assignee_and_leader_undo_preserve_same_record(self):
        for actor, assignee in (
            (self.assignee, self.assignee),
            (self.leader, self.assignee),
            (self.leader, None),
        ):
            with self.subTest(actor=actor.name, assignee=assignee):
                chore = self.make_chore(status=Chore.Status.COMPLETED, assignee=assignee)
                before, count = self.snapshot(chore), Chore.objects.count()
                self.select_member(actor)
                response = self.act(chore, "undo_completion")
                self.assert_success(
                    response, chore, before,
                    status=Chore.Status.IN_PROGRESS, completed_at=None,
                )
                self.assertEqual(Chore.objects.count(), count)

    def test_invalid_and_repeated_actions_preserve_complete_stored_row(self):
        self.select_member(self.leader)
        for status, actions in (
            (Chore.Status.OPEN, ("complete", "undo_completion")),
            (Chore.Status.IN_PROGRESS, ("claim", "start", "undo_completion")),
            (Chore.Status.COMPLETED, ("claim", "start", "complete")),
        ):
            chore = self.make_chore(status=status)
            before, count = self.snapshot(chore), Chore.objects.count()
            for action in (*actions, "open", "in_progress", "reopen", "archived", "", "unknown"):
                with self.subTest(status=status, action=action):
                    response = self.act(chore, action)
                    self.assertEqual(response.status_code, 400)
                    self.assertContains(response, 'role="alert"', status_code=400)
                    self.assert_unchanged(chore, before, count)
        self.assertEqual(self.act(chore, "undo_completion").status_code, 302)
        before = self.snapshot(chore)
        self.assertEqual(self.act(chore, "undo_completion").status_code, 400)
        self.assert_unchanged(chore, before, count)

    def test_action_payloads_cannot_smuggle_any_chore_fields(self):
        self.select_member(self.leader)
        extras = {
            **self.chore_data(),
            "creator": str(self.outsider.pk),
            "creator_id": str(self.outsider.pk),
            "assignee_id": str(self.outsider.pk),
            "status": "archived",
            "created_at": "2000-01-01T00:00:00Z",
            "completed_at": "2000-01-02T00:00:00Z",
        }
        for action, status in (
            ("claim", Chore.Status.OPEN),
            ("start", Chore.Status.OPEN),
            ("complete", Chore.Status.IN_PROGRESS),
            ("undo_completion", Chore.Status.COMPLETED),
        ):
            chore = self.make_chore(status=status, assignee=None)
            before, count = self.snapshot(chore), Chore.objects.count()
            for field, value in extras.items():
                with self.subTest(action=action, field=field):
                    self.assertEqual(
                        self.act(chore, action, **{field: value}).status_code, 400
                    )
                    self.assert_unchanged(chore, before, count)

    def test_completion_undo_and_recompletion_manage_event_timestamps(self):
        chore = self.make_chore(assignee=None)
        original = self.snapshot(chore)
        self.select_member(self.assignee)
        self.assertEqual(self.act(chore, "claim").status_code, 302)
        self.assertEqual(self.act(chore, "start").status_code, 302)
        self.assertIsNone(self.snapshot(chore)["completed_at"])
        first = datetime(2026, 9, 7, 10, tzinfo=UTC)
        second = datetime(2026, 9, 8, 11, tzinfo=UTC)
        with patch("chores.actions.timezone.now", return_value=first):
            self.assertEqual(self.act(chore, "complete").status_code, 302)
        before, count = self.snapshot(chore), Chore.objects.count()
        self.assertEqual(before["completed_at"], first)
        detail = self.client.get(self.detail_url(chore))
        self.assertContains(detail, first.isoformat())
        with patch("chores.actions.timezone.now", return_value=second):
            self.assertEqual(self.act(chore, "complete").status_code, 400)
            self.assert_unchanged(chore, before, count)
            self.assertEqual(self.act(chore, "undo_completion").status_code, 302)
            self.assertIsNone(self.snapshot(chore)["completed_at"])
            self.assertEqual(self.act(chore, "complete").status_code, 302)
        self.assertEqual(self.snapshot(chore)["completed_at"], second)
        self.assertEqual(self.snapshot(chore)["created_at"], original["created_at"])


class UndoEditingAndDetailTests(Task5TestCase):
    def test_undo_restores_each_separate_normal_edit_role_without_workflow_authority(self):
        for actor in (self.creator, self.assignee, self.leader, self.unrelated):
            with self.subTest(actor=actor.name):
                chore = self.make_chore(status=Chore.Status.COMPLETED)
                before, count = self.snapshot(chore), Chore.objects.count()
                self.select_member(actor)
                self.assertNotContains(
                    self.client.get(self.detail_url(chore)), self.edit_url(chore)
                )
                for method in ("get", "post"):
                    response = getattr(self.client, method)(
                        self.edit_url(chore), self.chore_data()
                    )
                    self.assertEqual(response.status_code, 403)
                    self.assert_unchanged(chore, before, count)
                self.select_member(self.leader)
                self.assertEqual(self.act(chore, "undo_completion").status_code, 302)
                self.select_member(actor)
                if actor == self.unrelated:
                    before = self.snapshot(chore)
                    self.assertEqual(self.client.get(self.edit_url(chore)).status_code, 403)
                    self.assertEqual(
                        self.client.post(self.edit_url(chore), self.chore_data()).status_code,
                        403,
                    )
                    self.assert_unchanged(chore, before, count)
                else:
                    self.assertEqual(self.client.get(self.edit_url(chore)).status_code, 200)
                    response = self.client.post(self.edit_url(chore), self.chore_data())
                    self.assertRedirects(response, self.detail_url(chore))
                    chore.refresh_from_db()
                    self.assertEqual(chore.title, "Wash the dishes")
                    self.assertEqual(chore.status, Chore.Status.IN_PROGRESS)
                    self.assertIsNone(chore.completed_at)
                if actor == self.creator:
                    before = self.snapshot(chore)
                    self.assertEqual(self.act(chore, "complete").status_code, 403)
                    self.assert_unchanged(chore, before, count)

    def test_leader_undo_preserves_deactivated_creator_and_assignee_references(self):
        chore = self.make_chore(status=Chore.Status.COMPLETED)
        before = self.snapshot(chore)
        self.select_member(self.leader)
        for member in (self.creator, self.assignee):
            self.assertEqual(
                self.client.post(
                    reverse("chores:member_deactivate", args=[member.pk])
                ).status_code, 302
            )
        self.assert_success(
            self.act(chore, "undo_completion"), chore, before,
            status=Chore.Status.IN_PROGRESS, completed_at=None,
        )
        detail = self.client.get(self.detail_url(chore))
        self.assertContains(detail, self.creator.name)
        self.assertContains(detail, self.assignee.name)
        choices = self.client.get(self.edit_url(chore)).context["form"].fields["assignee"]
        self.assertNotIn(self.assignee, choices.queryset)
        before, count = self.snapshot(chore), Chore.objects.count()
        self.select_member(self.assignee)
        self.assertRedirects(self.act(chore, "complete"), reverse("chores:home"))
        self.assertNotIn(CURRENT_MEMBER_SESSION_KEY, self.client.session)
        self.assert_unchanged(chore, before, count)
        self.select_member(self.leader)
        self.assertEqual(
            self.client.post(
                self.edit_url(chore), self.chore_data(assignee=str(self.inactive.pk))
            ).status_code, 400
        )
        self.assert_unchanged(chore, before, count)
        self.assertEqual(
            self.client.post(self.edit_url(chore), self.chore_data(assignee="")).status_code,
            302,
        )

    def test_detail_offers_only_the_exact_role_and_state_actions(self):
        for assignee in (None, self.assignee):
            for status in Chore.Status.values:
                chore = self.make_chore(status=status, assignee=assignee)
                for actor in (self.creator, self.assignee, self.leader, self.unrelated):
                    with self.subTest(assignee=assignee, status=status, actor=actor.name):
                        self.select_member(actor)
                        response = self.client.get(self.detail_url(chore))
                        expected = set()
                        if status == Chore.Status.OPEN and assignee is None:
                            expected.add("claim")
                        if actor == self.leader or actor == assignee:
                            expected.add({
                                Chore.Status.OPEN: "start",
                                Chore.Status.IN_PROGRESS: "complete",
                                Chore.Status.COMPLETED: "undo_completion",
                            }[status])
                        actual = {action for action, label in response.context["workflow_actions"]}
                        self.assertEqual(actual, expected)
                        for action in ("claim", "start", "complete", "undo_completion"):
                            assertion = self.assertContains if action in expected else self.assertNotContains
                            assertion(response, f'value="{action}"')
                        if "undo_completion" in expected:
                            self.assertContains(response, "Undo completion")


class ActionRequestBoundaryTests(Task5TestCase):
    def test_invalid_session_selections_never_mutate_actions(self):
        deleted = Member.objects.create(household=self.household, name="Deleted")
        deleted_id = str(deleted.pk)
        deleted.delete()
        for selection in (None, deleted_id, str(self.inactive.pk), str(self.outsider.pk), "bad-uuid", [], {}):
            for action, status in (
                ("claim", Chore.Status.OPEN),
                ("start", Chore.Status.OPEN),
                ("complete", Chore.Status.IN_PROGRESS),
                ("undo_completion", Chore.Status.COMPLETED),
            ):
                with self.subTest(selection=selection, action=action):
                    chore = self.make_chore(status=status, assignee=None)
                    before, count = self.snapshot(chore), Chore.objects.count()
                    session = self.client.session
                    session.pop(CURRENT_MEMBER_SESSION_KEY, None)
                    if selection is not None:
                        session[CURRENT_MEMBER_SESSION_KEY] = selection
                    session.save()
                    self.assertRedirects(self.act(chore, action), reverse("chores:home"))
                    self.assertNotIn(CURRENT_MEMBER_SESSION_KEY, self.client.session)
                    self.assert_unchanged(chore, before, count)

    def test_unknown_chore_or_outside_household_cannot_be_acted_on(self):
        chore = self.make_chore(creator=self.outsider, assignee=None)
        before, count = self.snapshot(chore), Chore.objects.count()
        self.select_member(self.leader)
        for action in ("claim", "start", "complete", "undo_completion"):
            for chore_id in (chore.pk, chore.pk + 1000):
                with self.subTest(action=action, chore_id=chore_id):
                    response = self.client.post(
                        reverse("chores:chore_action", args=[chore_id]), {"action": action}
                    )
                    self.assertEqual(response.status_code, 404)
                    self.assertNotContains(response, chore.title, status_code=404)
                    self.assert_unchanged(chore, before, count)

    def test_all_non_post_methods_reject_workflow_mutation(self):
        self.select_member(self.leader)
        chore = self.make_chore(assignee=None)
        before, count = self.snapshot(chore), Chore.objects.count()
        for method in ("get", "head", "put", "patch", "delete", "options"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.action_url(chore), {"action": "claim"})
                self.assertEqual(response.status_code, 405)
                self.assert_unchanged(chore, before, count)

    def test_csrf_is_required_and_rendered_token_allows_post(self):
        chore = self.make_chore(assignee=None)
        before, count = self.snapshot(chore), Chore.objects.count()
        client = Client(enforce_csrf_checks=True)
        session = client.session
        session[CURRENT_MEMBER_SESSION_KEY] = str(self.creator.pk)
        session.save()
        self.assertEqual(client.post(self.action_url(chore), {"action": "claim"}).status_code, 403)
        self.assert_unchanged(chore, before, count)
        response = client.get(self.detail_url(chore))
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        token = client.cookies["csrftoken"].value
        response = client.post(
            self.action_url(chore), {"action": "claim", "csrfmiddlewaretoken": token}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.snapshot(chore), dict(before, assignee_id=self.creator.pk))


class WorkflowDomainTests(Task5TestCase):
    def test_stale_domain_claims_recheck_persisted_assignment_and_status(self):
        chore = self.make_chore(assignee=None)
        stale = Chore.objects.get(pk=chore.pk)
        perform_chore_action(chore=chore, member=self.creator, action="claim")
        before, count = self.snapshot(chore), Chore.objects.count()
        with self.assertRaises(ValidationError):
            perform_chore_action(chore=stale, member=self.unrelated, action="claim")
        self.assert_unchanged(chore, before, count)
        for status in (Chore.Status.IN_PROGRESS, Chore.Status.COMPLETED):
            invalid = self.make_chore(status=status, assignee=None)
            before, count = self.snapshot(invalid), Chore.objects.count()
            with self.assertRaises(ValidationError):
                perform_chore_action(chore=invalid, member=self.leader, action="claim")
            self.assert_unchanged(invalid, before, count)

    def test_intervening_claim_between_domain_read_and_update_does_not_overwrite_winner(self):
        chore = self.make_chore(assignee=None)
        original_update = QuerySet.update
        winner = {}

        def competing_update(queryset, **changes):
            # Insert a competing write at the critical read/update boundary.
            original_update(Chore.objects.filter(pk=chore.pk), assignee_id=self.unrelated.pk)
            winner.update(self.snapshot(chore))
            return original_update(queryset, **changes)

        with patch.object(QuerySet, "update", competing_update):
            with self.assertRaises(ValidationError):
                perform_chore_action(chore=chore, member=self.creator, action="claim")
        self.assertEqual(self.snapshot(chore), winner)

    def test_domain_uses_current_assignee_and_active_identity(self):
        chore = self.make_chore()
        stale = Chore.objects.get(pk=chore.pk)
        Chore.objects.filter(pk=chore.pk).update(assignee=self.unrelated)
        before, count = self.snapshot(chore), Chore.objects.count()
        with self.assertRaises(PermissionDenied):
            perform_chore_action(chore=stale, member=self.assignee, action="start")
        self.assert_unchanged(chore, before, count)
        inactive_actor = Member.objects.get(pk=self.creator.pk)
        self.creator.deactivate()
        for action in ("claim", "start", "complete", "undo_completion"):
            with self.subTest(action=action):
                with self.assertRaises(PermissionDenied):
                    perform_chore_action(chore=chore, member=inactive_actor, action=action)
                self.assert_unchanged(chore, before, count)

    def test_domain_rejects_invalid_actions_wrong_states_and_foreign_household(self):
        for status in Chore.Status.values:
            chore = self.make_chore(status=status)
            before, count = self.snapshot(chore), Chore.objects.count()
            for action in ("open", "in_progress", "completed", "reopen", "unknown", None):
                with self.subTest(status=status, action=action):
                    with self.assertRaises(ValidationError):
                        perform_chore_action(chore=chore, member=self.leader, action=action)
                    self.assert_unchanged(chore, before, count)
            with self.assertRaises(Chore.DoesNotExist):
                perform_chore_action(chore=chore, member=self.outsider, action="start")
            self.assert_unchanged(chore, before, count)

    def test_claim_and_start_preserve_member_deactivation_guard(self):
        chore = self.make_chore(assignee=None)
        perform_chore_action(chore=chore, member=self.unrelated, action="claim")
        for action in (None, "start"):
            if action:
                perform_chore_action(chore=chore, member=self.unrelated, action=action)
            before, count = self.snapshot(chore), Chore.objects.count()
            with self.assertRaises(ValidationError):
                self.unrelated.deactivate()
            self.unrelated.refresh_from_db()
            self.assertTrue(self.unrelated.is_active)
            self.assert_unchanged(chore, before, count)

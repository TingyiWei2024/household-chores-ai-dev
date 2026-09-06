"""History, Reuse, and same-record Undo integration request tests."""

from datetime import date, timedelta
from unittest.mock import patch
from uuid import uuid4

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from chores.current_member import CURRENT_MEMBER_SESSION_KEY
from chores.models import Chore, Member
from chores.test_task4 import Task4TestCase


class Task7TestCase(Task4TestCase):
    def source(self, **overrides):
        return self.make_chore(status=Chore.Status.COMPLETED, **overrides)

    def reuse_url(self, chore):
        return reverse("chores:chore_reuse", args=[chore.pk])

    def rows(self, url, **params):
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        return {chore.pk for chore in response.context["chores"]}

    def history_rows(self):
        return self.rows(reverse("chores:history"))

    def board_rows(self, **params):
        return self.rows(reverse("chores:home"), **params)

    def stored_data(self):
        return (
            list(Chore.objects.order_by("pk").values()),
            list(Member.objects.order_by("pk").values()),
        )

    def source_payload(self, source, **overrides):
        data = {
            "title": source.title,
            "description": source.description,
            "assignee": str(source.assignee_id) if source.assignee_id else "",
            "due_date": source.due_date.isoformat() if source.due_date else "",
        }
        data.update(overrides)
        return data

    def successful_reuse(self, source, payload, actor):
        source_before = self.snapshot(source)
        members_before = list(Member.objects.order_by("pk").values())
        existing_ids = set(Chore.objects.values_list("pk", flat=True))
        # Keep the acting session unexpired while proving a distinct creation time.
        now = timezone.now() + timedelta(seconds=1)
        with patch("django.utils.timezone.now", return_value=now):
            response = self.client.post(self.reuse_url(source), payload)
        new = Chore.objects.exclude(pk__in=existing_ids).get()
        self.assertRedirects(response, self.detail_url(new))
        self.assertEqual(Chore.objects.count(), len(existing_ids) + 1)
        self.assertNotEqual(new.pk, source.pk)
        self.assertEqual(new.creator, actor)
        self.assertEqual(new.status, Chore.Status.OPEN)
        self.assertEqual(new.created_at, now)
        self.assertIsNone(new.completed_at)
        self.assertEqual(self.snapshot(source), source_before)
        self.assertEqual(list(Member.objects.order_by("pk").values()), members_before)
        self.assertIn(new.pk, self.board_rows())
        self.assertNotIn(source.pk, self.board_rows())
        self.assertIn(source.pk, self.history_rows())
        self.assertNotIn(new.pk, self.history_rows())
        return new


class HistoryAndUndoTests(Task7TestCase):
    def test_history_lists_only_household_completed_chores_for_every_role(self):
        completed = self.source(title="Completed household")
        opened = self.make_chore(title="Open household")
        progressing = self.make_chore(title="Progress household", status=Chore.Status.IN_PROGRESS)
        outside = self.source(title="Private outside history", creator=self.outsider)
        before = self.stored_data()
        for actor in (self.creator, self.assignee, self.leader, self.unrelated):
            with self.subTest(actor=actor.name):
                self.select_member(actor)
                response = self.client.get(reverse("chores:history"))
                self.assertEqual(self.history_rows(), {completed.pk})
                self.assertEqual(self.board_rows(), {opened.pk, progressing.pk})
                self.assertContains(response, "<h2>History</h2>", html=True)
                self.assertContains(response, self.detail_url(completed))
                self.assertContains(response, self.reuse_url(completed))
                self.assertContains(response, "Active board")
                self.assertNotContains(response, outside.title)
                self.assertContains(self.client.get(reverse("chores:home")), reverse("chores:history"))
        self.assertEqual(self.stored_data(), before)

    def test_empty_history_is_usable(self):
        response = self.client.get(reverse("chores:history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No completed chores yet.")
        self.assertContains(response, "Active board")
        self.assertContains(response, reverse("chores:chore_create"))

    def test_history_details_preserve_deactivated_names_and_all_stored_values(self):
        source = self.source()
        self.creator.deactivate()
        self.assignee.deactivate()
        self.select_member(self.leader)
        before = self.stored_data()
        history = self.client.get(reverse("chores:history"))
        self.assertContains(history, source.completed_at.isoformat())
        detail = self.client.get(self.detail_url(source))
        for value in (source.title, source.description, self.creator.name, self.assignee.name,
                      "Completed", source.due_date.isoformat(), source.created_at.isoformat(),
                      source.completed_at.isoformat()):
            self.assertContains(detail, value)
        self.assertEqual(self.stored_data(), before)
        unassigned = self.source(assignee=None, due_date=None, description="")
        detail = self.client.get(self.detail_url(unassigned))
        self.assertContains(detail, "Unassigned")
        self.assertContains(detail, "No due date")

    def test_assignee_and_leader_undo_restore_same_record_to_board_and_edit_roles(self):
        for actor in (self.assignee, self.leader):
            with self.subTest(actor=actor.name):
                source = self.source()
                before, count = self.snapshot(source), Chore.objects.count()
                self.select_member(actor)
                self.assertIn(source.pk, self.history_rows())
                response = self.client.post(
                    reverse("chores:chore_action", args=[source.pk]), {"action": "undo_completion"}
                )
                self.assertRedirects(response, self.detail_url(source))
                self.assertEqual(self.snapshot(source), dict(before, status=Chore.Status.IN_PROGRESS,
                                                            completed_at=None))
                self.assertEqual(Chore.objects.count(), count)
                self.assertNotIn(source.pk, self.history_rows())
                self.assertIn(source.pk, self.board_rows())
                self.assertIn(source.pk, self.board_rows(member=str(self.assignee.pk)))
                for editor in (self.creator, self.assignee, self.leader):
                    self.select_member(editor)
                    self.assertEqual(self.client.get(self.edit_url(source)).status_code, 200)
                    self.assertEqual(self.client.post(self.edit_url(source), self.chore_data()).status_code, 302)
                self.select_member(self.unrelated)
                before = self.stored_data()
                for method in ("get", "post"):
                    self.assertEqual(getattr(self.client, method)(self.edit_url(source), self.chore_data()).status_code,
                                     403)
                self.assertEqual(self.stored_data(), before)

    def test_denied_undo_preserves_source_history_and_board(self):
        source = self.source()
        for actor in (self.creator, self.unrelated):
            with self.subTest(actor=actor.name):
                self.select_member(actor)
                before = self.stored_data()
                response = self.client.post(
                    reverse("chores:chore_action", args=[source.pk]), {"action": "undo_completion"}
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(self.history_rows(), {source.pk})
                self.assertEqual(self.board_rows(), set())
                self.assertEqual(self.stored_data(), before)


class ReuseEligibilityAndPrefillTests(Task7TestCase):
    def test_each_role_can_reuse_completed_source_with_unchanged_normal_values(self):
        for actor in (self.creator, self.assignee, self.leader, self.unrelated):
            with self.subTest(actor=actor.name):
                source = self.source()
                self.select_member(actor)
                before = self.stored_data()
                detail = self.client.get(self.detail_url(source))
                self.assertContains(detail, self.reuse_url(source))
                self.assertNotContains(detail, self.edit_url(source))
                response = self.client.get(self.reuse_url(source))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "The completed chore stays unchanged.")
                self.assertEqual(self.stored_data(), before)
                new = self.successful_reuse(source, self.source_payload(source), actor)
                for field in ("title", "description", "assignee_id", "due_date"):
                    self.assertEqual(getattr(new, field), getattr(source, field))

    def test_active_chores_never_offer_or_allow_reuse(self):
        for status in (Chore.Status.OPEN, Chore.Status.IN_PROGRESS):
            source = self.make_chore(status=status)
            before = self.stored_data()
            for actor in (self.creator, self.assignee, self.leader, self.unrelated):
                with self.subTest(status=status, actor=actor.name):
                    self.select_member(actor)
                    self.assertNotContains(self.client.get(self.detail_url(source)), self.reuse_url(source))
                    for method in ("get", "post"):
                        response = getattr(self.client, method)(self.reuse_url(source), self.chore_data())
                        self.assertEqual(response.status_code, 400)
                        self.assertContains(response, "Only completed chores can be reused.", status_code=400)
                        self.assertEqual(self.stored_data(), before)

    def test_prefills_preserve_normal_values_and_only_active_assignees(self):
        for assignee in (self.assignee, self.inactive, None):
            for due_date, description in ((date(2000, 1, 1), "Historical details"), (None, "")):
                with self.subTest(assignee=assignee, due_date=due_date):
                    source = self.source(assignee=assignee, due_date=due_date, description=description)
                    before = self.stored_data()
                    response = self.client.get(self.reuse_url(source))
                    form = response.context["form"]
                    self.assertEqual(form["title"].value(), source.title)
                    self.assertEqual(form["description"].value(), description)
                    self.assertEqual(form["due_date"].value(), due_date)
                    self.assertEqual(form["assignee"].value(),
                                     assignee.pk if assignee and assignee.is_active else None)
                    self.assertEqual(list(form.fields), ["title", "description", "assignee", "due_date"])
                    self.assertIsNone(form.instance.pk)
                    self.assertEqual(self.stored_data(), before)
                    self.assertQuerySetEqual(form.fields["assignee"].queryset,
                                             [self.creator, self.assignee, self.leader, self.unrelated],
                                             ordered=False)
                    self.assertNotContains(response, f'<option value="{self.inactive.pk}"')
                    self.assertNotContains(response, f'<option value="{self.outsider.pk}"')

    def test_edited_and_cleared_reuse_supports_unassigned_self_other_and_leader(self):
        source = self.source()
        for assignee in (None, self.creator, self.unrelated, self.leader):
            with self.subTest(assignee=assignee):
                payload = self.chore_data(assignee=str(assignee.pk) if assignee else "")
                new = self.successful_reuse(source, payload, self.creator)
                self.assertEqual(new.title, "Wash the dishes")
                self.assertEqual(new.description, "Include the pans")
                self.assertEqual(new.due_date, date(2026, 11, 12))
                self.assertEqual(new.assignee, assignee)
        new = self.successful_reuse(source, {"title": "Cleared optional values"}, self.creator)
        self.assertEqual(new.description, "")
        self.assertIsNone(new.due_date)
        self.assertIsNone(new.assignee)

    def test_reuse_of_inactive_historical_members_preserves_source_and_member_records(self):
        source = self.source(creator=self.inactive, assignee=self.inactive)
        for description in (source.description, "Changed for new chore"):
            with self.subTest(description=description):
                before = self.stored_data()
                self.assertEqual(self.client.get(self.reuse_url(source)).status_code, 200)
                self.assertEqual(self.stored_data(), before)
                new = self.successful_reuse(
                    source, self.source_payload(source, assignee="", description=description), self.creator
                )
                self.assertIsNone(new.assignee)
                self.assertEqual(new.description, description)

    def test_protected_value_tampering_cannot_copy_identity_or_modify_source(self):
        source = self.source()
        self.select_member(self.unrelated)
        new = self.successful_reuse(source, self.chore_data(
            id=source.pk, pk=source.pk, source_id=source.pk,
            creator=str(self.leader.pk), creator_id=str(self.leader.pk),
            status=Chore.Status.COMPLETED, created_at=source.created_at.isoformat(),
            completed_at=source.completed_at.isoformat(),
        ), self.unrelated)
        self.assertNotEqual(new.created_at, source.created_at)
        before = self.stored_data()
        for method in ("get", "post"):
            self.assertEqual(getattr(self.client, method)(self.edit_url(source), self.chore_data()).status_code, 403)
        self.assertEqual(self.client.post(reverse("chores:chore_action", args=[source.pk]),
                                         {"action": "undo_completion"}).status_code, 403)
        self.assertEqual(self.stored_data(), before)


class ReuseValidationAndStaleRequestsTests(Task7TestCase):
    def test_invalid_inputs_preserve_all_existing_data_and_create_nothing(self):
        source = self.source()
        before = self.stored_data()
        payloads = [{"description": "Missing title"}]
        payloads += [self.chore_data(title=value) for value in ("", "  ", "x" * 201)]
        payloads += [self.chore_data(due_date=value) for value in ("bad-date", "2026-02-30")]
        payloads += [self.chore_data(assignee=value) for value in (
            str(uuid4()), "bad-uuid", str(self.inactive.pk), str(self.outsider.pk)
        )]
        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.post(self.reuse_url(source), payload)
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.context["form"].errors)
                self.assertContains(response, 'class="errorlist"', status_code=400)
                self.assertEqual(self.stored_data(), before)

    def test_assignee_deactivated_after_form_get_is_rejected_and_can_be_corrected(self):
        source = self.source()
        self.assertEqual(self.client.get(self.reuse_url(source)).status_code, 200)
        self.select_member(self.leader)
        self.assertEqual(self.client.post(reverse("chores:member_deactivate", args=[self.assignee.pk])).status_code, 302)
        self.select_member(self.creator)
        before = self.stored_data()
        response = self.client.post(self.reuse_url(source), self.source_payload(source))
        self.assertEqual(response.status_code, 400)
        self.assertIn("assignee", response.context["form"].errors)
        self.assertEqual(self.stored_data(), before)
        for assignee in (self.leader, None):
            new = self.successful_reuse(
                source, self.source_payload(source, assignee=str(assignee.pk) if assignee else ""), self.creator
            )
            self.assertEqual(new.assignee, assignee)

    def test_source_undone_after_form_get_rejects_stale_reuse_post(self):
        source = self.source()
        self.select_member(self.unrelated)
        self.assertEqual(self.client.get(self.reuse_url(source)).status_code, 200)
        self.select_member(self.leader)
        self.assertEqual(self.client.post(reverse("chores:chore_action", args=[source.pk]),
                                         {"action": "undo_completion"}).status_code, 302)
        self.select_member(self.unrelated)
        before = self.stored_data()
        self.assertEqual(self.client.post(self.reuse_url(source), self.chore_data()).status_code, 400)
        self.assertEqual(self.stored_data(), before)
        self.assertNotIn(source.pk, self.history_rows())
        self.assertIn(source.pk, self.board_rows())

    def test_current_member_at_submission_becomes_the_new_creator(self):
        source = self.source()
        self.assertEqual(self.client.get(self.reuse_url(source)).status_code, 200)
        self.select_member(self.unrelated)
        self.successful_reuse(source, self.source_payload(source), self.unrelated)


class HistoryReuseRequestBoundaryTests(Task7TestCase):
    def test_invalid_acting_selections_cannot_reuse_or_access_history(self):
        source = self.source()
        deleted = Member.objects.create(household=self.household, name="Deleted actor")
        deleted_id = str(deleted.pk)
        deleted.delete()
        before = self.stored_data()
        for value in (None, deleted_id, str(self.inactive.pk), str(self.outsider.pk), "bad-uuid", [], {}):
            for method, url in (("get", reverse("chores:history")),
                                ("get", self.reuse_url(source)), ("post", self.reuse_url(source))):
                with self.subTest(value=value, method=method, url=url):
                    session = self.client.session
                    session.pop(CURRENT_MEMBER_SESSION_KEY, None)
                    if value is not None:
                        session[CURRENT_MEMBER_SESSION_KEY] = value
                    session.save()
                    response = getattr(self.client, method)(url, self.chore_data())
                    self.assertRedirects(response, reverse("chores:home"))
                    self.assertNotIn(CURRENT_MEMBER_SESSION_KEY, self.client.session)
                    self.assertEqual(self.stored_data(), before)

    def test_missing_malformed_and_foreign_source_identifiers_are_rejected(self):
        source = self.source(creator=self.outsider, title="Private outside source")
        before = self.stored_data()
        for url in (self.reuse_url(source), "/chores/999999/reuse/", "/chores/bad-id/reuse/", "/chores/reuse/"):
            for method in ("get", "post"):
                with self.subTest(url=url, method=method):
                    response = getattr(self.client, method)(url, self.chore_data())
                    self.assertEqual(response.status_code, 404)
                    self.assertNotContains(response, source.title, status_code=404)
                    self.assertEqual(self.stored_data(), before)

    def test_unsupported_methods_and_get_reads_do_not_mutate_records(self):
        source = self.source()
        before = self.stored_data()
        self.assertEqual(self.client.get(reverse("chores:history")).status_code, 200)
        self.assertEqual(self.client.get(self.reuse_url(source), self.chore_data()).status_code, 200)
        for url, methods in ((reverse("chores:history"), ("post", "put", "patch", "delete", "options", "head")),
                             (self.reuse_url(source), ("put", "patch", "delete", "options", "head"))):
            for method in methods:
                with self.subTest(url=url, method=method):
                    self.assertEqual(getattr(self.client, method)(url, self.chore_data()).status_code, 405)
                    self.assertEqual(self.stored_data(), before)

    def test_reuse_post_requires_csrf_and_accepts_the_rendered_token(self):
        source = self.source()
        before = self.stored_data()
        client = Client(enforce_csrf_checks=True)
        session = client.session
        session[CURRENT_MEMBER_SESSION_KEY] = str(self.unrelated.pk)
        session.save()
        self.assertEqual(client.post(self.reuse_url(source), self.chore_data()).status_code, 403)
        self.assertEqual(self.stored_data(), before)
        response = client.get(self.reuse_url(source))
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertEqual(self.stored_data(), before)
        response = client.post(self.reuse_url(source), self.chore_data(
            csrfmiddlewaretoken=client.cookies["csrftoken"].value
        ))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Chore.objects.count(), 2)
        self.assertEqual(self.snapshot(source), before[0][0])

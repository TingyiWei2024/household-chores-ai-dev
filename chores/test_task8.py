"""Final cumulative acceptance flows through real, CSRF-protected requests."""

from datetime import date, timedelta
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from chores.current_member import CURRENT_MEMBER_SESSION_KEY
from chores.models import Chore, Household, Member


class MVPRequestTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.household, cls.leader = Household.objects.create_with_leader(
            household_name="Acceptance household", leader_name="Leader"
        )
        cls.creator = Member.objects.create(household=cls.household, name="Creator")
        cls.assignee = Member.objects.create(household=cls.household, name="Assignee")
        cls.other = Member.objects.create(household=cls.household, name="Other member")

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        date_patch = patch("django.utils.timezone.localdate", return_value=date(2026, 9, 9))
        date_patch.start()
        self.addCleanup(date_patch.stop)
        self.client.get(reverse("chores:home"))

    def post(self, url, data=None):
        return self.client.post(url, {
            **(data or {}), "csrfmiddlewaretoken": self.client.cookies["csrftoken"].value,
        })

    def select(self, member):
        response = self.post(reverse("chores:set_current_member"), {"member": str(member.pk)})
        self.assertRedirects(response, reverse("chores:home"))
        self.assertEqual(self.client.session[CURRENT_MEMBER_SESSION_KEY], str(member.pk))

    def detail_url(self, chore):
        return reverse("chores:chore_detail", args=[chore.pk])

    def act(self, chore, action):
        return self.post(reverse("chores:chore_action", args=[chore.pk]), {"action": action})

    def snapshot(self, chore):
        return Chore.objects.values().get(pk=chore.pk)

    def stored_data(self):
        return (list(Chore.objects.order_by("pk").values()),
                list(Member.objects.order_by("pk").values()),
                list(Household.objects.order_by("pk").values()))

    def normal_data(self, **extra):
        return {"title": "Clean the shared kitchen", "description": "Clean surfaces",
                "assignee": "", "due_date": "2026-09-08", **extra}

    def board(self, **params):
        response = self.client.get(reverse("chores:home"), params)
        self.assertEqual(response.status_code, 200)
        return response

    def history(self):
        response = self.client.get(reverse("chores:history"))
        self.assertEqual(response.status_code, 200)
        return response

    def row_ids(self, response):
        return {chore.pk for chore in response.context["chores"]}

    def create_claim_start_complete(self):
        """Perform every action under test through its actual application URL."""
        self.select(self.creator)
        board = self.board()
        self.assertContains(board, reverse("chores:chore_create"))
        form = self.client.get(reverse("chores:chore_create"))
        self.assertEqual(list(form.context["form"].fields),
                         ["title", "description", "assignee", "due_date"])
        count = Chore.objects.count()
        response = self.post(reverse("chores:chore_create"), self.normal_data())
        chore = Chore.objects.latest("pk")
        self.assertRedirects(response, self.detail_url(chore))
        self.assertEqual(Chore.objects.count(), count + 1)
        self.assertEqual(chore.creator, self.creator)
        self.assertEqual(chore.status, Chore.Status.OPEN)
        self.assertIsNone(chore.assignee)
        self.assertIsNone(chore.completed_at)
        self.assertIsNotNone(chore.created_at)
        self.assertIn(chore.pk, self.row_ids(self.board()))
        self.assertNotIn(chore.pk, self.row_ids(self.history()))

        self.select(self.assignee)
        self.assertContains(self.client.get(self.detail_url(chore)), 'value="claim"')
        before = self.snapshot(chore)
        self.assertRedirects(self.act(chore, "claim"), self.detail_url(chore))
        self.assertEqual(self.snapshot(chore), dict(before, assignee_id=self.assignee.pk))
        self.assertContains(self.client.get(self.detail_url(chore)), "Start work")
        before = self.snapshot(chore)
        self.assertRedirects(self.act(chore, "start"), self.detail_url(chore))
        self.assertEqual(self.snapshot(chore), dict(before, status=Chore.Status.IN_PROGRESS))
        self.assertContains(self.client.get(self.detail_url(chore)), "Complete chore")
        before = self.snapshot(chore)
        completed_at = timezone.now() + timedelta(seconds=1)
        with patch("django.utils.timezone.now", return_value=completed_at):
            response = self.act(chore, "complete")
        self.assertRedirects(response, self.detail_url(chore))
        self.assertEqual(self.snapshot(chore), dict(before, status=Chore.Status.COMPLETED,
                                                  completed_at=completed_at))
        self.assertContains(self.client.get(self.detail_url(chore)), completed_at.isoformat())
        self.assertNotIn(chore.pk, self.row_ids(self.board()))
        self.assertIn(chore.pk, self.row_ids(self.history()))
        chore.refresh_from_db()
        return chore


class CompleteMVPFlowTests(MVPRequestTestCase):
    def test_select_create_claim_start_complete_history_reuse_end_to_end(self):
        source = self.create_claim_start_complete()
        history = self.history()
        self.assertContains(history, self.detail_url(source))
        reuse_url = reverse("chores:chore_reuse", args=[source.pk])
        self.assertContains(history, reuse_url)
        board = self.board()
        self.assertEqual(board.context["indicators"]["completion_rate"], 100)
        self.assertEqual(board.context["indicators"]["overdue_count"], 0)

        self.select(self.other)
        detail = self.client.get(self.detail_url(source))
        self.assertContains(detail, reuse_url)
        self.assertNotContains(detail, 'value="undo_completion"')
        self.assertNotContains(detail, reverse("chores:chore_edit", args=[source.pk]))
        before = self.stored_data()
        form = self.client.get(reuse_url).context["form"]
        self.assertEqual(form["title"].value(), source.title)
        self.assertEqual(form["description"].value(), source.description)
        self.assertEqual(form["due_date"].value(), source.due_date)
        self.assertEqual(form["assignee"].value(), self.assignee.pk)
        self.assertEqual(self.stored_data(), before)
        new_created_at = source.completed_at + timedelta(seconds=1)
        with patch("django.utils.timezone.now", return_value=new_created_at):
            response = self.post(reuse_url, self.normal_data(assignee=str(self.assignee.pk)))
        new = Chore.objects.exclude(pk=source.pk).get()
        self.assertRedirects(response, self.detail_url(new))
        self.assertEqual(Chore.objects.count(), 2)
        self.assertNotEqual(new.pk, source.pk)
        self.assertEqual(new.creator, self.other)
        self.assertEqual(new.status, Chore.Status.OPEN)
        self.assertEqual(new.created_at, new_created_at)
        self.assertIsNone(new.completed_at)
        for field in ("title", "description", "due_date", "assignee_id"):
            self.assertEqual(getattr(new, field), getattr(source, field))
        self.assertEqual(self.snapshot(source), before[0][0])
        self.assertEqual(list(Member.objects.order_by("pk").values()), before[1])
        self.assertEqual(self.row_ids(self.board()), {new.pk})
        self.assertEqual(self.row_ids(self.history()), {source.pk})
        self.assertEqual(self.board().context["indicators"]["week_total"], 2)
        self.assertEqual(self.board().context["indicators"]["completion_rate"], 50)
        self.assertEqual(self.board().context["indicators"]["overdue_count"], 1)

    def test_integrated_undo_restores_roles_history_filter_and_kpis(self):
        for actor in (self.assignee, self.leader):
            with self.subTest(undo_actor=actor.name):
                source = self.create_claim_start_complete()
                count = Chore.objects.count()
                before = self.snapshot(source)
                original_metrics = self.board().context["indicators"]
                for denied in (self.creator, self.other):
                    self.select(denied)
                    history_ids = self.row_ids(self.history())
                    board_ids = self.row_ids(self.board())
                    self.assertEqual(self.act(source, "undo_completion").status_code, 403)
                    self.assertEqual(self.snapshot(source), before)
                    self.assertEqual(self.row_ids(self.history()), history_ids)
                    self.assertEqual(self.row_ids(self.board()), board_ids)
                for member in (self.creator, self.assignee, self.leader, self.other):
                    self.select(member)
                    edit_url = reverse("chores:chore_edit", args=[source.pk])
                    self.assertEqual(self.client.get(edit_url).status_code, 403)
                    self.assertEqual(self.post(edit_url, self.normal_data()).status_code, 403)
                    self.assertEqual(self.snapshot(source), before)
                self.select(actor)
                self.assertContains(self.client.get(self.detail_url(source)), "Undo completion")
                self.assertRedirects(self.act(source, "undo_completion"), self.detail_url(source))
                self.assertEqual(self.snapshot(source), dict(before, status=Chore.Status.IN_PROGRESS,
                                                            completed_at=None))
                self.assertEqual(Chore.objects.count(), count)
                self.assertNotIn(source.pk, self.row_ids(self.history()))
                self.assertIn(source.pk, self.row_ids(self.board()))
                self.assertIn(source.pk, self.row_ids(self.board(member=str(self.assignee.pk))))
                metrics = self.board().context["indicators"]
                self.assertEqual(metrics["week_total"], original_metrics["week_total"])
                self.assertEqual(metrics["week_completed"], original_metrics["week_completed"] - 1)
                self.assertEqual(metrics["overdue_count"], original_metrics["overdue_count"] + 1)
                for editor in (self.creator, self.assignee, self.leader):
                    self.select(editor)
                    self.assertEqual(self.client.get(edit_url).status_code, 200)
                    response = self.post(edit_url, self.normal_data(
                        title=f"Edited by {editor.name}", assignee=str(self.assignee.pk)
                    ))
                    self.assertRedirects(response, self.detail_url(source))
                    self.assertEqual(self.snapshot(source)["title"], f"Edited by {editor.name}")
                self.select(self.other)
                edited = self.snapshot(source)
                self.assertEqual(self.post(edit_url, self.normal_data()).status_code, 403)
                self.assertEqual(self.snapshot(source), edited)
                self.select(self.assignee)
                second_completion = before["completed_at"] + timedelta(seconds=2)
                with patch("django.utils.timezone.now", return_value=second_completion):
                    response = self.act(source, "complete")
                self.assertRedirects(response, self.detail_url(source))
                self.assertEqual(self.snapshot(source)["completed_at"], second_completion)
                self.assertEqual(self.snapshot(source)["created_at"], before["created_at"])
                self.assertIn(source.pk, self.row_ids(self.history()))
                self.assertNotIn(source.pk, self.row_ids(self.board()))


class CumulativeBoundaryTests(MVPRequestTestCase):
    def test_reassignment_or_unassignment_removes_active_deactivation_block(self):
        for start in (False, True):
            for replacement in (self.other, None):
                with self.subTest(start=start, replacement=replacement):
                    self.select(self.leader)
                    name = f"Temporary member {start} {replacement}"
                    self.assertRedirects(self.post(reverse("chores:member_add"), {"name": name}),
                                         reverse("chores:member_list"))
                    member = Member.objects.get(name=name)
                    response = self.post(reverse("chores:chore_create"),
                                         self.normal_data(assignee=str(member.pk)))
                    chore = Chore.objects.latest("pk")
                    self.assertRedirects(response, self.detail_url(chore))
                    if start:
                        self.assertRedirects(self.act(chore, "start"), self.detail_url(chore))
                    before = self.stored_data()
                    deactivate_url = reverse("chores:member_deactivate", args=[member.pk])
                    self.assertEqual(self.post(deactivate_url).status_code, 400)
                    self.assertEqual(self.stored_data(), before)
                    self.assertRedirects(self.post(reverse("chores:chore_edit", args=[chore.pk]),
                                                   self.normal_data(assignee=str(replacement.pk) if replacement else "")),
                                         self.detail_url(chore))
                    changed = self.snapshot(chore)
                    self.assertRedirects(self.post(deactivate_url), reverse("chores:member_list"))
                    member.refresh_from_db()
                    self.assertFalse(member.is_active)
                    self.assertEqual(self.snapshot(chore), changed)
                    self.assertTrue(Member.objects.filter(pk=member.pk).exists())

    def test_stale_assignee_on_create_and_edit_is_revalidated(self):
        self.select(self.creator)
        self.assertEqual(self.post(reverse("chores:chore_create"), self.normal_data()).status_code, 302)
        chore = Chore.objects.get()
        edit_url = reverse("chores:chore_edit", args=[chore.pk])
        self.assertEqual(self.client.get(reverse("chores:chore_create")).status_code, 200)
        self.assertEqual(self.client.get(edit_url).status_code, 200)
        self.select(self.leader)
        self.assertEqual(self.post(reverse("chores:member_deactivate", args=[self.other.pk])).status_code, 302)
        self.select(self.creator)
        before = self.stored_data()
        for url in (reverse("chores:chore_create"), edit_url):
            with self.subTest(url=url):
                response = self.post(url, self.normal_data(assignee=str(self.other.pk)))
                self.assertEqual(response.status_code, 400)
                self.assertIn("assignee", response.context["form"].errors)
                self.assertEqual(self.stored_data(), before)

    def test_identity_member_management_and_normal_chore_posts_enforce_csrf(self):
        self.select(self.leader)
        self.assertEqual(self.post(reverse("chores:chore_create"), self.normal_data()).status_code, 302)
        chore = Chore.objects.get()
        before = self.stored_data()
        for url, data in (
            (reverse("chores:set_current_member"), {"member": str(self.other.pk)}),
            (reverse("chores:member_add"), {"name": "Unauthorized addition"}),
            (reverse("chores:member_rename", args=[self.other.pk]), {"name": "Changed"}),
            (reverse("chores:member_deactivate", args=[self.other.pk]), {}),
            (reverse("chores:chore_create"), self.normal_data()),
            (reverse("chores:chore_edit", args=[chore.pk]), self.normal_data(title="Changed")),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, data).status_code, 403)
                self.assertEqual(self.stored_data(), before)
                self.assertEqual(self.client.session[CURRENT_MEMBER_SESSION_KEY], str(self.leader.pk))

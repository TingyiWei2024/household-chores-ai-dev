"""Data models for the chores app."""

import uuid

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class HouseholdManager(models.Manager):
    """Create the circular household/leader relationship atomically."""

    def create_with_leader(self, *, household_name, leader_name):
        household = self.model(name=household_name)
        leader = Member(name=leader_name, household_id=household.pk)
        household.leader_id = leader.pk

        household.clean_fields(exclude={"leader"})

        with transaction.atomic():
            # Household and Member have required references to each other. Their
            # UUIDs let both sides be assigned before either row is inserted,
            # and the database checks the deferred foreign key at commit time.
            models.Model.save(household, force_insert=True)
            leader.save(force_insert=True)
            household.full_clean()

        return household, leader


class Household(models.Model):
    """The group whose members share chores."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    leader = models.OneToOneField(
        "Member",
        on_delete=models.PROTECT,
        related_name="led_household",
    )

    objects = HouseholdManager()

    def clean(self):
        super().clean()
        if self.leader_id and self.pk:
            leader = Member.objects.filter(pk=self.leader_id).first()
            if leader is None or leader.household_id != self.pk:
                raise ValidationError(
                    {"leader": "The leader must be a member of this household."}
                )
            if not leader.is_active:
                raise ValidationError(
                    {"leader": "The household leader must be active."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Member(models.Model):
    """A leader or regular member of a household."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="members",
    )
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    @property
    def is_leader(self):
        if not self.pk or not self.household_id:
            return False
        return Household.objects.filter(
            pk=self.household_id,
            leader_id=self.pk,
        ).exists()

    def clean(self):
        super().clean()
        if self.pk and not self.is_active:
            if Household.objects.filter(leader_id=self.pk).exists():
                raise ValidationError(
                    {"is_active": "The household leader must remain active."}
                )
            if self.assigned_chores.exclude(
                status=Chore.Status.COMPLETED
            ).exists():
                raise ValidationError(
                    {
                        "is_active": (
                            "A member with assigned non-completed chores "
                            "cannot be deactivated."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def deactivate(self):
        """Deactivate a regular member after checking all domain guards."""
        if self._state.adding:
            raise ValidationError(
                {"is_active": "An unsaved member cannot be deactivated."}
            )

        with transaction.atomic():
            stored_member = type(self).objects.select_for_update().get(pk=self.pk)
            stored_member.is_active = False
            stored_member.save(update_fields={"is_active"})

        self.is_active = False

    def __str__(self):
        return self.name


class Chore(models.Model):
    """A unit of household work."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    creator = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name="created_chores",
    )
    assignee = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name="assigned_chores",
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    due_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=("open", "in_progress", "completed")
                ),
                name="chore_has_valid_status",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="completed", completed_at__isnull=False)
                    | (
                        ~models.Q(status="completed")
                        & models.Q(completed_at__isnull=True)
                    )
                ),
                name="chore_completion_timestamp_matches_status",
            ),
        ]

    @property
    def is_overdue(self):
        return (
            self.due_date is not None
            and self.due_date < timezone.localdate()
            and self.status != self.Status.COMPLETED
        )

    def save(self, *args, **kwargs):
        if self.status == self.Status.COMPLETED:
            if self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"completed_at"}

        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title

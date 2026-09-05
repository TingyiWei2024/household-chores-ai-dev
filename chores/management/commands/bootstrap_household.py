"""Create the initial development household and leader."""

from django.core.management.base import BaseCommand

from chores.models import Household


class Command(BaseCommand):
    help = "Create the initial household and leader in an empty database."

    def add_arguments(self, parser):
        parser.add_argument("--household-name", default="My Household")
        parser.add_argument("--leader-name", default="Leader")

    def handle(self, *args, **options):
        if Household.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "A household already exists; bootstrap made no changes."
                )
            )
            return

        household, leader = Household.objects.create_with_leader(
            household_name=options["household_name"],
            leader_name=options["leader_name"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Created household "{household.name}" with leader "{leader.name}".'
            )
        )

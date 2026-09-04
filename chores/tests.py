from django.apps import apps
from django.test import SimpleTestCase


class ChoresAppSmokeTest(SimpleTestCase):
    def test_app_is_registered(self):
        self.assertEqual(apps.get_app_config("chores").name, "chores")

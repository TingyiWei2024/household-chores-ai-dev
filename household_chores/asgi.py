"""ASGI config for the household_chores project."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "household_chores.settings")

application = get_asgi_application()

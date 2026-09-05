"""URL configuration for the household_chores project."""

from django.urls import include, path

urlpatterns = [
    path("", include("chores.urls")),
]

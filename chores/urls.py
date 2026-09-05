"""URLs for the chores app."""

from django.urls import path

from chores import views

app_name = "chores"

urlpatterns = [
    path("", views.home, name="home"),
    path("current-member/", views.set_current_member, name="set_current_member"),
    path("members/", views.member_list, name="member_list"),
    path("members/add/", views.member_add, name="member_add"),
    path(
        "members/<uuid:member_id>/rename/",
        views.member_rename,
        name="member_rename",
    ),
    path(
        "members/<uuid:member_id>/deactivate/",
        views.member_deactivate,
        name="member_deactivate",
    ),
]

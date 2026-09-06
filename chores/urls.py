"""URLs for the chores app."""

from django.urls import path

from chores import views

app_name = "chores"

urlpatterns = [
    path("", views.home, name="home"),
    path("current-member/", views.set_current_member, name="set_current_member"),
    path("history/", views.history, name="history"),
    path("chores/create/", views.chore_create, name="chore_create"),
    path("chores/<int:chore_id>/", views.chore_detail, name="chore_detail"),
    path("chores/<int:chore_id>/edit/", views.chore_edit, name="chore_edit"),
    path("chores/<int:chore_id>/reuse/", views.chore_reuse, name="chore_reuse"),
    path("chores/<int:chore_id>/actions/", views.chore_action, name="chore_action"),
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

# MVP verification

This maps the numbered acceptance criteria in the frozen [specification](plan.md).
It is a coverage reference, not a competing issue queue or a QA verdict. Run the
complete suite on the revision under review; record its full commit hash, actual
commands/results and limitations in the selected issue's Engineer/QA comments.
An earlier checkpoint's result does not verify a later revision. Any required
check that cannot run is **BLOCKED / NOT VERIFIED**.

## Specification coverage

Implementation paths below are relative to the repository root. Test labels use
these module aliases: `T2` = `chores.tests`, `T3` = `chores.test_task3`, through
`T8` = `chores.test_task8`. Replace the alias to run an individual dotted label
with `uv run python manage.py test <label>`. Every named test below also runs in
the full suite.

| Spec AC | Implementation and complete behavior | Named automated evidence |
| --- | --- | --- |
| 1 | `chores/views.py` member management and `leader_required`; `chores/models.py` Leader/deactivation guards: Leader adds/renames/deactivates regular members, can rename self, cannot deactivate self; regular members denied. | `T3.MemberManagementTests.test_leader_can_add_regular_member`, `T3.MemberManagementTests.test_leader_can_rename_regular_member`, `T3.MemberManagementTests.test_leader_can_rename_the_leader`, `T3.MemberManagementTests.test_member_removal_is_deactivation_not_deletion`, `T3.MemberManagementTests.test_leader_cannot_be_deactivated`; all methods in `T3.MemberManagementPermissionTests`. |
| 2 | `chores/views.py:chore_create`, `chores/forms.py:ChoreForm`: selected member creates a distinct Open chore with current creator and generated timestamps; required title and protected fields validated. | `T4.ChoreCreationTests.test_regular_member_and_leader_can_create_all_assignment_cases`, `T4.ChoreCreationTests.test_creation_ignores_crafted_protected_fields`, `T4.ChoreFormValidationTests.test_invalid_creation_reports_errors_and_creates_no_record`, `T8.CompleteMVPFlowTests.test_select_create_claim_start_complete_history_reuse_end_to_end`. |
| 3 | `chores/forms.py:ChoreForm`, `chores/views.py:chore_create/chore_edit/chore_reuse`: optional assignment, active household choices only, server-side validation on every submission; invalid edit preserves the entire record. | `T4.ChoreCreationTests.test_regular_member_and_leader_can_create_all_assignment_cases`, `T4.ChoreEditPermissionTests.test_assign_reassign_and_clear_optional_fields_in_both_active_states`, `T4.ChoreFormValidationTests.test_forms_expose_only_normal_fields_and_active_household_assignees`, `T4.ChoreFormValidationTests.test_invalid_assignment_and_reassignment_leave_every_stored_field_unchanged`, `T8.CumulativeBoundaryTests.test_stale_assignee_on_create_and_edit_is_revalidated`, `T7.ReuseValidationAndStaleRequestsTests.test_assignee_deactivated_after_form_get_is_rejected_and_can_be_corrected`. |
| 4 | `chores/actions.py:perform_chore_action`: any selected active member can claim only an unassigned Open chore; conditional persisted-state update prevents overwriting a competing winner. | `T5.ClaimRequestTests.test_creator_other_regular_member_and_leader_can_claim`, `T5.ClaimRequestTests.test_assigned_in_progress_and_completed_claims_are_rejected`, `T5.ClaimRequestTests.test_stale_claim_form_cannot_replace_first_claimant`, `T5.WorkflowDomainTests.test_intervening_claim_between_domain_read_and_update_does_not_overwrite_winner`, `T8.CompleteMVPFlowTests.test_select_create_claim_start_complete_history_reuse_end_to_end`. |
| 5 | `chores/actions.py:perform_chore_action/available_chore_actions`: only current assignee or Leader can advance Open → In Progress → Completed; stale assignment and skipped transitions rejected. | `T5.WorkflowRequestTests.test_separate_assignee_and_leader_roles_perform_forward_actions`, `T5.WorkflowRequestTests.test_creator_only_and_unrelated_members_cannot_change_workflow`, `T5.WorkflowRequestTests.test_old_assignee_cannot_start_or_complete_after_reassignment_or_unassignment`, `T5.WorkflowRequestTests.test_invalid_and_repeated_actions_preserve_complete_stored_row`. |
| 6 | `chores/views.py:_can_edit_chore/chore_edit`, `chores/forms.py:ChoreForm`, `chores/templates/chores/chore_detail.html`: creator, assignee, Leader edit only normal fields in both active states; all roles read-only while Completed. | `T4.ChoreEditPermissionTests.test_separate_creator_assignee_and_leader_roles_can_edit_both_active_states`, `T4.ChoreEditPermissionTests.test_assign_reassign_and_clear_optional_fields_in_both_active_states`, `T4.ChoreEditPermissionTests.test_completed_normal_fields_are_read_only_for_each_separate_role`, `T8.CompleteMVPFlowTests.test_integrated_undo_restores_roles_history_filter_and_kpis`. |
| 7 | `chores/views.py:_can_edit_chore/chore_edit`: unrelated and former assignees denied without changing any persisted fields, including timestamps. | `T4.ChoreEditPermissionTests.test_unrelated_member_cannot_get_or_submit_edits_in_either_active_state`, `T4.ChoreEditPermissionTests.test_old_assignee_loses_edit_permission_after_reassignment_or_unassignment`, `T8.CompleteMVPFlowTests.test_integrated_undo_restores_roles_history_filter_and_kpis`. |
| 8 | `chores/models.py:Chore.due_date`, `chores/forms.py:ChoreForm`: date is optional, editable/clearable, and invalid dates rejected. | `T2.ChoreModelTests.test_optional_fields_are_stored`, `T4.ChoreCreationTests.test_optional_fields_may_be_omitted`, `T4.ChoreEditPermissionTests.test_assign_reassign_and_clear_optional_fields_in_both_active_states`, `T4.ChoreFormValidationTests.test_invalid_creation_reports_errors_and_creates_no_record`. |
| 9 | `chores/models.py:Chore.is_overdue`, `chores/templates/chores/home.html`: due strictly before application today and non-Completed; no extra stored status. Due today, future, missing date and Completed are excluded. | `T2.ChoreModelTests.test_overdue_is_derived_with_strict_due_date_boundary`, `T6.IndicatorAndDateTests.test_overdue_rows_and_count_use_strict_date_and_noncompleted_status`. |
| 10 | `chores/views.py:history/_board_context`, `chores/actions.py:perform_chore_action`: current Completed membership only; Undo preserves identity, sets In Progress, clears completion timestamp and restores board/filter membership. | `T7.HistoryAndUndoTests.test_history_lists_only_household_completed_chores_for_every_role`, `T7.HistoryAndUndoTests.test_assignee_and_leader_undo_restore_same_record_to_board_and_edit_roles`, `T8.CompleteMVPFlowTests.test_integrated_undo_restores_roles_history_filter_and_kpis`. |
| 11 | `chores/views.py:chore_reuse`, `chores/forms.py:ChoreForm`: any selected member reuses Completed source into new Open identity/current creator/fresh timestamps; source unchanged, normal values editable/clearable, active assignee prefilled or inactive left Unassigned. | `T7.ReuseEligibilityAndPrefillTests.test_each_role_can_reuse_completed_source_with_unchanged_normal_values`, `T7.ReuseEligibilityAndPrefillTests.test_prefills_preserve_normal_values_and_only_active_assignees`, `T7.ReuseEligibilityAndPrefillTests.test_edited_and_cleared_reuse_supports_unassigned_self_other_and_leader`, `T7.ReuseEligibilityAndPrefillTests.test_protected_value_tampering_cannot_copy_identity_or_modify_source`, `T7.ReuseValidationAndStaleRequestsTests.test_source_undone_after_form_get_rejects_stale_reuse_post`, `T8.CompleteMVPFlowTests.test_select_create_claim_start_complete_history_reuse_end_to_end`. |
| 12 | `chores/views.py:_board_context`, `chores/forms.py:BoardFilterForm`, `chores/templates/chores/home.html`: all household active rows, assignee filter/reset, unassigned/no-date visibility; filter never changes acting identity or household indicators. | `T6.SharedBoardAndFilterTests.test_every_acting_member_sees_all_household_active_chores`, `T6.SharedBoardAndFilterTests.test_member_filter_uses_assignee_and_reset_restores_unassigned`, `T6.SharedBoardAndFilterTests.test_filter_includes_household_members_without_changing_acting_or_assignment_choices`, `T6.SharedBoardAndFilterTests.test_invalid_filters_show_errors_without_data_or_identity_changes`. |
| 13 | `chores/board.py:household_indicators`: inclusive Monday–Sunday due-date denominator, Completed numerator; independent of assignment, filter, creation/completion date. Covers zero/some/all, week/month/year edges. | `T6.IndicatorAndDateTests.test_monday_sunday_and_month_year_crossover_boundaries`, `T6.IndicatorAndDateTests.test_weekly_ratio_includes_all_statuses_and_ignores_record_timestamps`, `T6.IndicatorAndDateTests.test_zero_and_all_completed_rates_are_distinct_from_no_eligible_work`, `T6.IndicatorAndDateTests.test_household_indicators_do_not_follow_member_filter_or_acting_identity`. |
| 14 | `chores/board.py:household_indicators`, `chores/templates/chores/home.html`: whole-household count of overdue non-Completed chores; completion/Undo updates count and board together. | `T6.IndicatorAndDateTests.test_overdue_rows_and_count_use_strict_date_and_noncompleted_status`, `T6.IndicatorAndDateTests.test_household_indicators_do_not_follow_member_filter_or_acting_identity`, `T6.BoardWorkflowIntegrationTests.test_completion_and_undo_update_board_and_both_indicators`, `T8.CompleteMVPFlowTests.test_integrated_undo_restores_roles_history_filter_and_kpis`. |
| 15 | `chores/board.py:household_indicators`, `chores/templates/chores/home.html`: no-date chores excluded; empty denominator displays exact `No chores due this week`, distinct from 0%. | `T6.IndicatorAndDateTests.test_weekly_ratio_includes_all_statuses_and_ignores_record_timestamps`, `T6.IndicatorAndDateTests.test_no_eligible_chores_has_exact_message_instead_of_zero_percentage`, `T6.IndicatorAndDateTests.test_zero_and_all_completed_rates_are_distinct_from_no_eligible_work`. |
| 16 | `chores/current_member.py`, `chores/middleware.py`, `chores/forms.py:CurrentMemberForm/ChoreForm`: inactive identities/assignees excluded; invalid or stale selected identities clear/prompt without mutation. | `T3.CurrentMemberTests.test_selector_contains_only_active_household_members`, `T3.CurrentMemberTests.test_inactive_member_cannot_be_selected_by_crafted_request`, `T3.CurrentMemberTests.test_stale_inactive_session_selection_is_cleared`, `T4.ChoreNavigationAndSelectionTests.test_invalid_session_selections_prompt_without_any_chore_mutation`, `T4.ChoreFormValidationTests.test_invalid_assignment_and_reassignment_leave_every_stored_field_unchanged`, `T7.HistoryReuseRequestBoundaryTests.test_invalid_acting_selections_cannot_reuse_or_access_history`. |
| 17 | `chores/models.py:Member.deactivate/save`, `chores/views.py:member_deactivate/chore_edit`: active assigned Open/In Progress blocks removal without row changes; reassignment or unassignment removes that block. | `T3.DeactivationGuardTests.test_open_assigned_chore_blocks_deactivation`, `T3.DeactivationGuardTests.test_in_progress_assigned_chore_blocks_deactivation`, `T3.DeactivationGuardTests.test_rejected_deactivation_does_not_mutate_member_or_chore`, `T3.DeactivationGuardTests.test_model_save_also_rejects_deactivation_with_active_assignment`, `T8.CumulativeBoundaryTests.test_reassignment_or_unassignment_removes_active_deactivation_block`. |
| 18 | `chores/models.py:Member`, `chores/views.py:history/chore_detail/chore_reuse`, History/detail templates: Completed doesn't block deactivation, member rows/references persist and names remain visible, including after Leader Undo. | `T3.DeactivationGuardTests.test_completed_assigned_chore_does_not_block_deactivation`, `T4.ChoreDetailTests.test_historical_creator_and_assignee_remain_visible_after_deactivation`, `T7.HistoryAndUndoTests.test_history_details_preserve_deactivated_names_and_all_stored_values`, `T7.ReuseEligibilityAndPrefillTests.test_reuse_of_inactive_historical_members_preserves_source_and_member_records`, `T5.UndoEditingAndDetailTests.test_leader_undo_preserves_deactivated_creator_and_assignee_references`. |
| 19 | `chores/actions.py:perform_chore_action`, `chores/views.py:_can_edit_chore`: creator field-edit authority never grants workflow or Undo authority. | `T5.WorkflowRequestTests.test_creator_only_and_unrelated_members_cannot_change_workflow`, `T5.UndoEditingAndDetailTests.test_undo_restores_each_separate_normal_edit_role_without_workflow_authority`, `T8.CompleteMVPFlowTests.test_integrated_undo_restores_roles_history_filter_and_kpis`. |
| 20 | `chores/actions.py:perform_chore_action`, `chores/views.py:chore_edit/chore_reuse`: only assignee/Leader Undo mutates Completed source; normal edits/rejected actions preserve complete row, Undo restores In Progress edit roles, recompletion records a new event. Reuse only creates another record. | `T4.ChoreEditPermissionTests.test_completed_normal_fields_are_read_only_for_each_separate_role`, `T5.WorkflowRequestTests.test_assignee_and_leader_undo_preserve_same_record`, `T5.WorkflowRequestTests.test_invalid_and_repeated_actions_preserve_complete_stored_row`, `T5.WorkflowRequestTests.test_completion_undo_and_recompletion_manage_event_timestamps`, `T8.CompleteMVPFlowTests.test_integrated_undo_restores_roles_history_filter_and_kpis`. |
| 21 | `chores/models.py:Chore.Status`, `chores/actions.py:perform_chore_action`, `chores/forms.py:ChoreForm`: exactly three approved statuses, no backward transition except explicit Completed → In Progress Undo; arbitrary/tampered statuses cannot bypass guards. | `T2.ChoreModelTests.test_status_choices_are_exactly_the_approved_values`, `T2.ChoreModelTests.test_invalid_status_is_rejected_by_model_and_database`, `T5.WorkflowRequestTests.test_invalid_and_repeated_actions_preserve_complete_stored_row`, `T5.WorkflowRequestTests.test_action_payloads_cannot_smuggle_any_chore_fields`, `T5.WorkflowDomainTests.test_domain_rejects_invalid_actions_wrong_states_and_foreign_household`. |

Additional request boundaries run in `T5.ActionRequestBoundaryTests` and
`T7.HistoryReuseRequestBoundaryTests`: invalid identities, foreign/malformed
resources, unsupported methods, CSRF and whole-row non-mutation. The explicit
`T8.CumulativeBoundaryTests.test_identity_member_management_and_normal_chore_posts_enforce_csrf`
extends CSRF checks to identity selection, member management, creation and editing.
`T7.ReuseValidationAndStaleRequestsTests.test_invalid_inputs_preserve_all_existing_data_and_create_nothing`
checks required fields, invalid dates/assignees and complete source preservation.

## Run the cumulative checks

```shell
uv run python manage.py test chores.test_task8 --verbosity 2
uv run python manage.py test
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
git diff --check
```

After committing, also check the reviewed range with
`git diff --check <accepted-base-commit> HEAD`. Inspect the cumulative paths/diff
against the approved specification, including unchanged dependency declarations,
lockfile, frozen plan, backlog and workflow documents. Do not change those files
to make a check pass.

## Reproduce a clean setup from the exact commit

Run from the repository after the intended revision is committed. Exporting
tracked source avoids copying the development `.venv`, database or session data.
Use a new temporary directory for each revision; record the printed directory
and full hash in the issue report. Python and uv must already be available.

```shell
VERIFY_COMMIT=$(git rev-parse HEAD)
VERIFY_DIR=$(mktemp -d /tmp/chores-mvp-verify.XXXXXX)
git archive "$VERIFY_COMMIT" | tar -x -C "$VERIFY_DIR"
printf '%s\n%s\n' "$VERIFY_COMMIT" "$VERIFY_DIR"
cd "$VERIFY_DIR"
test ! -e .venv && test ! -e db.sqlite3
# Optional if the default cache is inaccessible; keep this distinct from .venv.
export UV_CACHE_DIR=/private/tmp/task4-pilot-uv-cache
uv sync
uv run python manage.py migrate
uv run python manage.py bootstrap_household \
  --household-name "My Household" --leader-name "Household Leader"
uv run python manage.py shell -c 'import json; from chores.models import Household, Member; h = Household.objects.get(); m = Member.objects.get(); assert h.leader_id == m.pk and m.is_active and m.household_id == h.pk; print(json.dumps([list(Household.objects.values()), list(Member.objects.values())], default=str, sort_keys=True))' > "$VERIFY_DIR.bootstrap-before.json"
uv run python manage.py bootstrap_household \
  --household-name "My Household" --leader-name "Household Leader"
uv run python manage.py shell -c 'import json; from chores.models import Household, Member; h = Household.objects.get(); m = Member.objects.get(); assert h.leader_id == m.pk and m.is_active and m.household_id == h.pk; print(json.dumps([list(Household.objects.values()), list(Member.objects.values())], default=str, sort_keys=True))' > "$VERIFY_DIR.bootstrap-after.json"
cmp "$VERIFY_DIR.bootstrap-before.json" "$VERIFY_DIR.bootstrap-after.json"
uv run python manage.py test
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py runserver 127.0.0.1:8765 --noreload
```

While that server runs, use another terminal for an actual HTTP request:

```shell
curl --fail --silent --show-error -o /tmp/chores-mvp-home.html \
  -w '%{http_code}\n' http://127.0.0.1:8765/
```

Expect HTTP 200 and the rendered Current Member selector with Household Leader.
Stop the server with Ctrl-C afterward. If the port is occupied, choose another
local port and record it. Record Python/uv/Django versions, fresh environment
path, isolated database path and installation output; verify exported tracked
source (especially `uv.lock`) remains identical to the recorded commit. Compare
the development database checksum before/after without opening or migrating it.
Reuse of a download cache is compatible with a fresh project environment;
reusing the development environment or database is not this check.

## Browser acceptance walkthrough

Use the isolated server above for throwaway data. Current Member represents the
acting household member; it is the MVP's simulated identity, without login.

1. Select Household Leader, open **Manage members**, and add Alice, Bob and Cara.
2. Select Alice. **Create chore** with a title and optional description/date,
   leaving **Unassigned**. Confirm Open and the stored details.
3. Select Bob; open the chore from the board, **Claim**, **Start work**, then
   **Complete chore**. Confirm Bob's assignment and the completion timestamp;
   the record leaves the board and appears in **History**.
4. Select Cara. Open that history record and **Reuse chore**. Check the prefills,
   edit or clear fields, and save. The new record is Open with Cara as creator;
   the completed source and its timestamp remain in History.
5. On the source, Cara and creator-only Alice cannot edit or Undo. Select Bob or
   the Leader and **Undo completion**. The same record returns to the board as
   In Progress, leaves History and clears the timestamp. Alice, Bob and Leader
   can edit normal fields again; Cara cannot. Complete again as Bob/Leader.
6. Filter the board by Bob and then clear it. Current Member and household
   indicators stay unchanged. A past-due active chore is overdue; due today is
   not. Weekly eligibility follows Monday–Sunday due dates. No dates in the
   current week displays **No chores due this week**.

Rendered request tests and actual HTTP startup checks provide executable UI
evidence. Record any additional interactive-browser run separately; if browser
control is unavailable, mark that supplementary check **BLOCKED / NOT VERIFIED**
without claiming it ran or omitting required checks above.

# Bugtracker – Bug Report

**Date:** 2026-10-28
**What was tested:** the `bugs` app (models, forms, views, URLs, templates) and `bugtracker/settings.py`
**Application code changed:** none. I only added test files and this report.

## Results at a glance

- **11 confirmed bugs.** Each one has at least one failing test.
- **6 things not confirmed.** They might be bugs or they might be on purpose, so the app owner needs to decide.
- **Many things checked that work correctly.** Their tests pass.

| Test run | Tests | Failed | Passed |
|---|---|---|---|
| Unit tests (`bugs/tests.py`) | 40 | 14 | 26 |
| Browser tests (`functional_tests/tests.py`, Playwright) | 3 | 2 | 1 |
| **Total** | **43** | **16** | **27** |

Every failing test fails because of a bug. Each one has a `# POSSIBLE BUG:` comment above the line that fails.

### How to run the tests

From the `bugtracker` folder:

```
venv\Scripts\python manage.py test bugs               # unit tests
venv\Scripts\python manage.py test functional_tests   # browser tests (Chromium)
venv\Scripts\python manage.py test                    # all tests
```

The tests use a temporary database, so `db.sqlite3` is never touched.

---

## Confirmed bugs

### Bug 1: Any logged-in user can edit any bug

**Severity:** High (security)

**In simple words:** Only Developers see an "Edit" button, but the button is just hidden. A Reporter can type `/bug_update/<id>/` into the address bar and change any bug, even one written by another person.

**Cause:**
- [bugs/views.py:89-96](bugs/views.py#L89-L96): `bug_update` only has `@login_required`. It never checks the user's role or who owns the bug.
- [templates/bugs/bug_list.html:50-53](templates/bugs/bug_list.html#L50-L53): the role check is only in the template, so it just hides the link.

**Tests:**
- [bugs/tests.py:45](bugs/tests.py#L45) `test_reporter_cannot_edit_another_users_bug`: a Reporter changes the title of another user's bug to "Hacked", and the change is saved.
- [functional_tests/tests.py:103](functional_tests/tests.py#L103) `test_reporter_cannot_edit_bug_by_typing_the_url`: in the browser, the edit form opens for the Reporter.

---

### Bug 2: Any logged-in user can delete any bug

**Severity:** High (security, data loss)

**In simple words:** This is the same problem as Bug 1, but for deleting. A Reporter can open `/bug/<id>/delete/` and delete any bug.

**Cause:** [bugs/views.py:99-102](bugs/views.py#L99-L102). `BugDeleteView` only uses `LoginRequiredMixin`. It has no role or owner check, for example no `get_queryset` filter and no `UserPassesTestMixin`.

**Test:** [bugs/tests.py:61](bugs/tests.py#L61) `test_reporter_cannot_delete_another_users_bug`

---

### Bug 3: The API shows all bugs to people who are not logged in

**Severity:** High (security, data leak)

**In simple words:** Anyone on the internet can open `/api/bugs/` or `/api/bugs/<id>/` without logging in. They see every bug with its full details and user IDs.

**Cause:**
- [bugs/views.py:119-125](bugs/views.py#L119-L125): `BugListAPI` and `BugDetailAPI` have no `permission_classes`.
- [bugtracker/settings.py](bugtracker/settings.py) has no `REST_FRAMEWORK` setting. Because of that, Django REST Framework uses its default, `AllowAny`.

**Tests:**
- [bugs/tests.py:74](bugs/tests.py#L74) `test_anonymous_user_cannot_list_bugs`: the API answers 200 instead of 401 or 403.
- [bugs/tests.py:82](bugs/tests.py#L82) `test_anonymous_user_cannot_read_bug_detail`: the API answers 200 instead of 401 or 403.

---

### Bug 4: Through the API, Reporters can see other people's bugs

**Severity:** Medium (security)

**In simple words:** On the Bug List page, a Reporter only sees their own bugs. The API ignores that rule and gives them every bug.

**Cause:** [bugs/views.py:120](bugs/views.py#L120) and [bugs/views.py:124](bugs/views.py#L124). Both API views use `BugReport.objects.all()`. They don't filter by role the way `bug_list` does at [bugs/views.py:59-62](bugs/views.py#L59-L62).

**Test:** [bugs/tests.py:90](bugs/tests.py#L90) `test_reporter_does_not_see_other_users_bugs_in_api`. Alice gets both Alice's bug and Bob's bug.

---

### Bug 5: The home page crashes for users without a profile

**Severity:** High (crash)

**In simple words:** A user created with `createsuperuser` or the admin panel has no role profile. When that user logs in and opens the home page, they get a "Server Error (500)".

**Cause:** [bugs/views.py:20](bugs/views.py#L20). `UserProfile.objects.get(user=request.user)` raises `DoesNotExist` when there is no profile. Only the register view creates profiles ([bugs/views.py:111](bugs/views.py#L111)), so every other way of creating a user leaves the user without one.

**Test:** [bugs/tests.py:111](bugs/tests.py#L111) `test_home_page_works_for_user_without_profile`. The page answers 500 instead of 200.

---

### Bug 6: The Bug List page crashes for users without a profile

**Severity:** High (crash)

**In simple words:** This has the same cause as Bug 5, on a different page. An admin user who opens "Bug List" gets a "Server Error (500)".

**Cause:** [bugs/views.py:59](bugs/views.py#L59). `request.user.userprofile.role` raises `RelatedObjectDoesNotExist` when the profile is missing.

**Test:** [bugs/tests.py:116](bugs/tests.py#L116) `test_bug_list_works_for_user_without_profile`. The page answers 500 instead of 200.

---

### Bug 7: The filter dropdowns forget what you chose

**Severity:** Low (usability)

**In simple words:** On the Bug List, you choose "Resolved" and click Filter. The list is filtered correctly, but the dropdown jumps back to "All Statuses". It looks as if no filter is active.

**Cause:** the view and the template use different variable names.
- [bugs/views.py:71-72](bugs/views.py#L71-L72) sends `status_filter` and `severity_filter`.
- [templates/bugs/bug_list.html:12-14](templates/bugs/bug_list.html#L12-L14) and [templates/bugs/bug_list.html:18-21](templates/bugs/bug_list.html#L18-L21) check `selected_status` and `selected_severity`. Those variables don't exist, so no option is ever marked `selected`.

**Tests:**
- [bugs/tests.py:126](bugs/tests.py#L126) `test_status_dropdown_remembers_selected_value`
- [bugs/tests.py:131](bugs/tests.py#L131) `test_severity_dropdown_remembers_selected_value`
- [functional_tests/tests.py:81](functional_tests/tests.py#L81) `test_filter_dropdown_keeps_chosen_status`: in the browser, the dropdown shows "" instead of "Resolved".

---

### Bug 8: For Reporters, the Bug List table has an extra column

**Severity:** Low (display)

**In simple words:** For Reporters, the table header has 6 columns but every row has 7 cells. The last cell is an empty cell with no header, so the table looks broken.

**Cause:**
- [templates/bugs/bug_list.html:35-37](templates/bugs/bug_list.html#L35-L37): the "Actions" `<th>` is inside `{% if ... == "Developer" %}`.
- [templates/bugs/bug_list.html:49-54](templates/bugs/bug_list.html#L49-L54): the matching `<td>` is outside the `if`, so it is always rendered. Only its contents are hidden.

**Test:** [bugs/tests.py:143](bugs/tests.py#L143) `test_reporter_rows_have_same_number_of_cells_as_header` (the row has 7 cells, the header 6).

---

### Bug 9: For Developers, the "No bugs reported." row is too short

**Severity:** Low (display)

**In simple words:** When the list is empty, Developers see 7 columns, but the "No bugs reported." row only stretches across 6 of them.

**Cause:** [templates/bugs/bug_list.html:58](templates/bugs/bug_list.html#L58). `colspan="6"` is fixed. It doesn't count the extra "Actions" column that Developers see.

**Test:** [bugs/tests.py:154](bugs/tests.py#L154) `test_empty_message_spans_all_developer_columns`

---

### Bug 10: Unassigned bugs show the word "None"

**Severity:** Low (display)

**In simple words:** If nobody is assigned to a bug, the "Assigned To" column shows the word "None" instead of being empty or saying something like "Unassigned".

**Cause:** [templates/bugs/bug_list.html:48](templates/bugs/bug_list.html#L48). `{{ bug.assigned_to }}` prints Python's `None` as text. It needs something like `|default:"Unassigned"`.

**Test:** [bugs/tests.py:162](bugs/tests.py#L162) `test_unassigned_bug_does_not_show_none`

---

### Bug 11: The Create and Edit pages have an empty heading

**Severity:** Low (display)

**In simple words:** When you report or edit a bug, the page has no title. There is an empty heading where "Report Bug" or "Edit Bug" should be.

**Cause:** [templates/bugs/bug_form.html:4](templates/bugs/bug_form.html#L4) shows `{{ form_title }}`, but neither [bugs/views.py:87](bugs/views.py#L87) (`bug_create`) nor [bugs/views.py:96](bugs/views.py#L96) (`bug_update`) passes `form_title` to the template.

**Tests:**
- [bugs/tests.py:177](bugs/tests.py#L177) `test_create_page_has_a_heading`
- [bugs/tests.py:183](bugs/tests.py#L183) `test_edit_page_has_a_heading`

---

## Not confirmed

These things look suspicious, but nothing in the code or README says they are wrong. They could be on purpose. Where possible, a test proves the behaviour exists. Those tests **pass** because they describe what the app does now: [bugs/tests.py:197](bugs/tests.py#L197) `NotConfirmedBehaviourTest`.

| # | What happens | Where | Why not confirmed |
|---|---|---|---|
| N1 | A Reporter's dashboard counts **all** bugs in the system, but their Bug List only shows their own. | [bugs/views.py:26](bugs/views.py#L26) | The dashboard could be meant as a team-wide overview. Test: `test_reporter_dashboard_counts_bugs_of_other_users`. |
| N2 | A Reporter can set the status (even "Resolved") and the assignee when creating a bug. | [bugs/forms.py:10](bugs/forms.py#L10) | The app has no written rule about who may change these fields. Test: `test_reporter_can_set_status_and_assignee_when_creating`. |
| N3 | The "Assigned to" dropdown offers every user, including Reporters. | [bugs/models.py:30](bugs/models.py#L30), [bugs/forms.py:10](bugs/forms.py#L10) | Assigning bugs to Reporters might be allowed. Test: `test_assigned_to_dropdown_offers_reporters`. |
| N4 | Two accounts can register with the same email, and the email is optional. | [bugs/forms.py:12-21](bugs/forms.py#L12-L21) | This is Django's normal behaviour, and the app never uses email. Test: `test_two_accounts_can_share_one_email`. |
| N5 | Unsafe settings: the secret key is in the code, `ALLOWED_HOSTS = ['*']` accepts any host, and `DEBUG = False` means `runserver` doesn't serve static files, so the banner image is missing during local development. | [bugtracker/settings.py:21](bugtracker/settings.py#L21), [24](bugtracker/settings.py#L24), [26-28](bugtracker/settings.py#L26-L28) | These are deployment settings, not app behaviour. Production may override them (there is Docker and nginx config). No test written. |
| N6 | The model's default reporter is "the first user in the database". In the admin, a new bug comes pre-filled with that unrelated user as reporter. If there are no users at all, the default is `None` and saving would fail. Chart.js is also loaded twice, with no version pinned. | [bugs/models.py:7-9](bugs/models.py#L7-L9), [bugs/models.py:31](bugs/models.py#L31), [templates/base.html:13](templates/base.html#L13), [templates/base.html:114](templates/base.html#L114) | The web form always sets the real reporter, and that is tested and works. The admin path and the double script load cause no visible error. No test written. |

---

## Checked: works correctly

These tests pass.

| Area | What was checked | Test |
|---|---|---|
| Home | Uses `home.html`. A logged-in user with a profile sees "name (Role)" in the navbar. | [bugs/tests.py:255](bugs/tests.py#L255), [259](bugs/tests.py#L259) |
| Register | Creates a profile with the chosen role. | [bugs/tests.py:278](bugs/tests.py#L278) |
| Register | Logs the new user in and redirects to the home page. | [bugs/tests.py:283](bugs/tests.py#L283) |
| Register | Mismatched passwords create no user. | [bugs/tests.py:288](bugs/tests.py#L288) |
| Login required | Dashboard, Bug List, Create, Edit and Delete all send anonymous visitors to `/login/?next=...`. | [bugs/tests.py:302](bugs/tests.py#L302) |
| Create bug | A valid form is saved and redirects to the Bug List. | [bugs/tests.py:317](bugs/tests.py#L317), [329](bugs/tests.py#L329) |
| Create bug | The reporter is the logged-in user, not the model's "first user" default. | [bugs/tests.py:322](bugs/tests.py#L322) |
| Create bug | A missing title is rejected. | [bugs/tests.py:334](bugs/tests.py#L334) |
| Bug List | Reporters only see their own bugs. Developers see all bugs. | [bugs/tests.py:347](bugs/tests.py#L347), [353](bugs/tests.py#L353) |
| Bug List | The status and severity filters return the right bugs. | [bugs/tests.py:359](bugs/tests.py#L359), [365](bugs/tests.py#L365) |
| Bug List | The Edit and Delete links are hidden from Reporters. | [bugs/tests.py:371](bugs/tests.py#L371) |
| Edit / Delete | A Developer can edit a bug, and editing keeps the original reporter. | [bugs/tests.py:384](bugs/tests.py#L384), [391](bugs/tests.py#L391) |
| Edit / Delete | A Developer can delete a bug and is redirected to the Bug List. | [bugs/tests.py:396](bugs/tests.py#L396) |
| Edit / Delete | Editing a bug that doesn't exist gives 404. | [bugs/tests.py:401](bugs/tests.py#L401) |
| Dashboard | The status, severity and "you vs. others" counts are correct. | [bugs/tests.py:414](bugs/tests.py#L414) |
| Dashboard | The chart data in the page is valid JSON. | [bugs/tests.py:420](bugs/tests.py#L420) |
| Logout | Logout with POST logs the user out and goes to the home page. | [bugs/tests.py:429](bugs/tests.py#L429) |
| Browser flow | Register as a Developer, see the name in the navbar, report a bug, and see it in the list with the right project and reporter. | [functional_tests/tests.py:48](functional_tests/tests.py#L48) |

---

## Files added

- [bugs/tests.py](bugs/tests.py): unit tests (Django `TestCase` and test client). This file replaced the empty placeholder.
- [functional_tests/\_\_init\_\_.py](functional_tests/__init__.py) and [functional_tests/tests.py](functional_tests/tests.py): Playwright browser tests (`StaticLiveServerTestCase`, sync API).
- `bug_report.md`: this report.

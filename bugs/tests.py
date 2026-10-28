import json
import re

from django.contrib.auth.models import User
from django.test import TestCase

from bugs.models import BugReport, UserProfile


def make_user(username, role=None):
    user = User.objects.create_user(username=username, password="S3cret-pass-123")
    if role:
        UserProfile.objects.create(user=user, role=role)
    return user


def make_bug(reporter, title="A bug", status="Open", severity="Low", **extra):
    return BugReport.objects.create(
        title=title,
        description="Something is broken",
        status=status,
        severity=severity,
        project="Demo",
        reporter=reporter,
        **extra,
    )


VALID_BUG_DATA = {
    "title": "New bug",
    "description": "Steps to reproduce",
    "status": "Open",
    "severity": "High",
    "project": "Demo",
    "assigned_to": "",
}


# ---------------------------------------------------------------------------
# Tests that reproduce bugs (expected to FAIL until the app is fixed)
# ---------------------------------------------------------------------------


class BugUpdatePermissionTest(TestCase):
    def test_reporter_cannot_edit_another_users_bug(self):
        alice = make_user("alice", "Reporter")
        bob = make_user("bob", "Reporter")
        bug = make_bug(bob, title="Bob's bug")
        self.client.force_login(alice)

        self.client.post(
            f"/bug_update/{bug.id}/", data={**VALID_BUG_DATA, "title": "Hacked"}
        )

        bug.refresh_from_db()
        # POSSIBLE BUG: bug_update has no role/owner check, any logged-in user can edit any bug
        self.assertEqual(bug.title, "Bob's bug")


class BugDeletePermissionTest(TestCase):
    def test_reporter_cannot_delete_another_users_bug(self):
        alice = make_user("alice", "Reporter")
        bob = make_user("bob", "Reporter")
        bug = make_bug(bob)
        self.client.force_login(alice)

        self.client.post(f"/bug/{bug.id}/delete/")

        # POSSIBLE BUG: BugDeleteView only checks login, any logged-in user can delete any bug
        self.assertTrue(BugReport.objects.filter(id=bug.id).exists())


class BugApiPermissionTest(TestCase):
    def test_anonymous_user_cannot_list_bugs(self):
        make_bug(make_user("bob", "Reporter"))

        response = self.client.get("/api/bugs/")

        # POSSIBLE BUG: the API has no permission classes, anonymous visitors get all bugs
        self.assertIn(response.status_code, [401, 403])

    def test_anonymous_user_cannot_read_bug_detail(self):
        bug = make_bug(make_user("bob", "Reporter"))

        response = self.client.get(f"/api/bugs/{bug.id}/")

        # POSSIBLE BUG: the API has no permission classes, anonymous visitors can read any bug
        self.assertIn(response.status_code, [401, 403])

    def test_reporter_does_not_see_other_users_bugs_in_api(self):
        alice = make_user("alice", "Reporter")
        make_bug(alice, title="Alice's bug")
        make_bug(make_user("bob", "Reporter"), title="Bob's bug")
        self.client.force_login(alice)

        response = self.client.get("/api/bugs/")

        titles = [bug["title"] for bug in response.json()]
        # POSSIBLE BUG: the API returns all bugs, while the Bug List page hides other reporters' bugs
        self.assertEqual(titles, ["Alice's bug"])


class UserWithoutProfileTest(TestCase):
    """Users created with createsuperuser or the admin have no UserProfile."""

    def setUp(self):
        self.client.raise_request_exception = False
        self.user = make_user("admin_like_user")  # no profile
        self.client.force_login(self.user)

    def test_home_page_works_for_user_without_profile(self):
        response = self.client.get("/")
        # POSSIBLE BUG: home() uses UserProfile.objects.get(), which raises DoesNotExist -> 500
        self.assertEqual(response.status_code, 200)

    def test_bug_list_works_for_user_without_profile(self):
        response = self.client.get("/bug_list/")
        # POSSIBLE BUG: bug_list() reads request.user.userprofile, which raises -> 500
        self.assertEqual(response.status_code, 200)


class BugListFilterFormTest(TestCase):
    def setUp(self):
        self.client.force_login(make_user("dev", "Developer"))

    def test_status_dropdown_remembers_selected_value(self):
        response = self.client.get("/bug_list/?status=Resolved")
        # POSSIBLE BUG: template checks "selected_status" but the view sends "status_filter"
        self.assertContains(response, 'value="Resolved" selected')

    def test_severity_dropdown_remembers_selected_value(self):
        response = self.client.get("/bug_list/?severity=Critical")
        # POSSIBLE BUG: template checks "selected_severity" but the view sends "severity_filter"
        self.assertContains(response, 'value="Critical" selected')


class BugListTableLayoutTest(TestCase):
    def count_cells(self, html):
        header = re.search(r"<thead.*?</thead>", html, re.S).group(0)
        first_row = re.search(r"<tbody>\s*<tr>(.*?)</tr>", html, re.S).group(1)
        return header.count("<th>"), first_row.count("<td")

    def test_reporter_rows_have_same_number_of_cells_as_header(self):
        reporter = make_user("alice", "Reporter")
        make_bug(reporter)
        self.client.force_login(reporter)

        response = self.client.get("/bug_list/")

        header_cells, row_cells = self.count_cells(response.content.decode())
        # POSSIBLE BUG: the "Actions" <td> is always rendered, but the <th> only for Developers
        self.assertEqual(row_cells, header_cells)

    def test_empty_message_spans_all_developer_columns(self):
        self.client.force_login(make_user("dev", "Developer"))

        response = self.client.get("/bug_list/")

        # POSSIBLE BUG: Developers see 7 columns but the empty row uses colspan="6"
        self.assertContains(response, 'colspan="7"')

    def test_unassigned_bug_does_not_show_none(self):
        dev = make_user("dev", "Developer")
        make_bug(dev, assigned_to=None)
        self.client.force_login(dev)

        response = self.client.get("/bug_list/")

        # POSSIBLE BUG: {{ bug.assigned_to }} prints the word "None" for unassigned bugs
        self.assertNotContains(response, "<td>None</td>")


class BugFormHeadingTest(TestCase):
    def get_heading(self, response):
        return re.search(r"<h2[^>]*>(.*?)</h2>", response.content.decode(), re.S).group(1)

    def test_create_page_has_a_heading(self):
        self.client.force_login(make_user("alice", "Reporter"))
        response = self.client.get("/bug_create/")
        # POSSIBLE BUG: template uses {{ form_title }} but bug_create() never passes it
        self.assertNotEqual(self.get_heading(response).strip(), "")

    def test_edit_page_has_a_heading(self):
        dev = make_user("dev", "Developer")
        bug = make_bug(dev)
        self.client.force_login(dev)
        response = self.client.get(f"/bug_update/{bug.id}/")
        # POSSIBLE BUG: template uses {{ form_title }} but bug_update() never passes it
        self.assertNotEqual(self.get_heading(response).strip(), "")


# ---------------------------------------------------------------------------
# Not confirmed: the behaviour exists (these tests pass), but it may be intended
# ---------------------------------------------------------------------------


class NotConfirmedBehaviourTest(TestCase):
    def test_reporter_dashboard_counts_bugs_of_other_users(self):
        alice = make_user("alice", "Reporter")
        make_bug(alice)
        make_bug(make_user("bob", "Reporter"))
        make_bug(make_user("carol", "Reporter"))
        self.client.force_login(alice)

        response = self.client.get("/dashboard/")

        # Bug List shows Alice 1 bug, but the dashboard counts all 3
        self.assertEqual(response.context["total_bugs"], [3, 0, 0])

    def test_reporter_can_set_status_and_assignee_when_creating(self):
        alice = make_user("alice", "Reporter")
        dev = make_user("dev", "Developer")
        self.client.force_login(alice)

        self.client.post(
            "/bug_create/",
            data={**VALID_BUG_DATA, "status": "Resolved", "assigned_to": dev.id},
        )

        bug = BugReport.objects.get()
        self.assertEqual(bug.status, "Resolved")
        self.assertEqual(bug.assigned_to, dev)

    def test_assigned_to_dropdown_offers_reporters(self):
        make_user("reporter_only", "Reporter")
        self.client.force_login(make_user("dev", "Developer"))

        response = self.client.get("/bug_create/")

        self.assertContains(response, ">reporter_only</option>")

    def test_two_accounts_can_share_one_email(self):
        for username in ["first", "second"]:
            self.client.post(
                "/register/",
                data={
                    "username": username,
                    "email": "same@example.com",
                    "password1": "S3cret-pass-123",
                    "password2": "S3cret-pass-123",
                    "role": "Reporter",
                },
            )
            self.client.logout()

        self.assertEqual(User.objects.filter(email="same@example.com").count(), 2)


# ---------------------------------------------------------------------------
# Checked: works correctly (expected to PASS)
# ---------------------------------------------------------------------------


class HomePageTest(TestCase):
    def test_uses_home_template(self):
        response = self.client.get("/")
        self.assertTemplateUsed(response, "home.html")

    def test_logged_in_user_with_profile_sees_home(self):
        self.client.force_login(make_user("alice", "Reporter"))
        response = self.client.get("/")
        self.assertContains(response, "alice (Reporter)")


class RegisterTest(TestCase):
    def post_registration(self, role="Developer"):
        return self.client.post(
            "/register/",
            data={
                "username": "newuser",
                "email": "new@example.com",
                "password1": "S3cret-pass-123",
                "password2": "S3cret-pass-123",
                "role": role,
            },
        )

    def test_registration_creates_profile_with_chosen_role(self):
        self.post_registration(role="Developer")
        profile = UserProfile.objects.get(user__username="newuser")
        self.assertEqual(profile.role, "Developer")

    def test_registration_logs_user_in_and_redirects_home(self):
        response = self.post_registration()
        self.assertRedirects(response, "/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), User.objects.get().id)

    def test_registration_with_mismatched_passwords_creates_nothing(self):
        self.client.post(
            "/register/",
            data={
                "username": "newuser",
                "password1": "S3cret-pass-123",
                "password2": "different-456",
                "role": "Reporter",
            },
        )
        self.assertEqual(User.objects.count(), 0)


class LoginRequiredTest(TestCase):
    def test_protected_pages_redirect_anonymous_to_login(self):
        bug = make_bug(make_user("bob", "Reporter"))
        for url in [
            "/dashboard/",
            "/bug_list/",
            "/bug_create/",
            f"/bug_update/{bug.id}/",
            f"/bug/{bug.id}/delete/",
        ]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, f"/login/?next={url}")


class BugCreateTest(TestCase):
    def test_can_save_a_POST_request(self):
        self.client.force_login(make_user("alice", "Reporter"))
        self.client.post("/bug_create/", data=VALID_BUG_DATA)
        self.assertEqual(BugReport.objects.get().title, "New bug")

    def test_reporter_is_the_logged_in_user(self):
        make_user("first_user", "Developer")  # would be the model default
        alice = make_user("alice", "Reporter")
        self.client.force_login(alice)
        self.client.post("/bug_create/", data=VALID_BUG_DATA)
        self.assertEqual(BugReport.objects.get().reporter, alice)

    def test_redirects_to_bug_list_after_POST(self):
        self.client.force_login(make_user("alice", "Reporter"))
        response = self.client.post("/bug_create/", data=VALID_BUG_DATA)
        self.assertRedirects(response, "/bug_list/")

    def test_invalid_data_is_not_saved(self):
        self.client.force_login(make_user("alice", "Reporter"))
        self.client.post("/bug_create/", data={**VALID_BUG_DATA, "title": ""})
        self.assertEqual(BugReport.objects.count(), 0)


class BugListTest(TestCase):
    def setUp(self):
        self.alice = make_user("alice", "Reporter")
        self.bob = make_user("bob", "Reporter")
        make_bug(self.alice, title="Alice open", status="Open", severity="Low")
        make_bug(self.bob, title="Bob resolved", status="Resolved", severity="High")

    def test_reporter_sees_only_own_bugs(self):
        self.client.force_login(self.alice)
        response = self.client.get("/bug_list/")
        self.assertContains(response, "Alice open")
        self.assertNotContains(response, "Bob resolved")

    def test_developer_sees_all_bugs(self):
        self.client.force_login(make_user("dev", "Developer"))
        response = self.client.get("/bug_list/")
        self.assertContains(response, "Alice open")
        self.assertContains(response, "Bob resolved")

    def test_status_filter(self):
        self.client.force_login(make_user("dev", "Developer"))
        response = self.client.get("/bug_list/?status=Resolved")
        self.assertNotContains(response, "Alice open")
        self.assertContains(response, "Bob resolved")

    def test_severity_filter(self):
        self.client.force_login(make_user("dev", "Developer"))
        response = self.client.get("/bug_list/?severity=Low")
        self.assertContains(response, "Alice open")
        self.assertNotContains(response, "Bob resolved")

    def test_edit_and_delete_buttons_hidden_from_reporter(self):
        self.client.force_login(self.alice)
        response = self.client.get("/bug_list/")
        self.assertNotContains(response, "/bug_update/")
        self.assertNotContains(response, "/delete/")


class DeveloperEditDeleteTest(TestCase):
    def setUp(self):
        self.dev = make_user("dev", "Developer")
        self.bug = make_bug(make_user("alice", "Reporter"), title="Old title")
        self.client.force_login(self.dev)

    def test_developer_can_edit_bug(self):
        self.client.post(
            f"/bug_update/{self.bug.id}/", data={**VALID_BUG_DATA, "title": "New title"}
        )
        self.bug.refresh_from_db()
        self.assertEqual(self.bug.title, "New title")

    def test_edit_keeps_original_reporter(self):
        self.client.post(f"/bug_update/{self.bug.id}/", data=VALID_BUG_DATA)
        self.bug.refresh_from_db()
        self.assertEqual(self.bug.reporter.username, "alice")

    def test_developer_can_delete_bug(self):
        response = self.client.post(f"/bug/{self.bug.id}/delete/")
        self.assertRedirects(response, "/bug_list/")
        self.assertEqual(BugReport.objects.count(), 0)

    def test_edit_missing_bug_returns_404(self):
        response = self.client.get("/bug_update/9999/")
        self.assertEqual(response.status_code, 404)


class DashboardTest(TestCase):
    def setUp(self):
        self.dev = make_user("dev", "Developer")
        make_bug(self.dev, status="Open", severity="Low", assigned_to=self.dev)
        make_bug(self.dev, status="Open", severity="High")
        make_bug(self.dev, status="Resolved", severity="Critical")
        self.client.force_login(self.dev)

    def test_counts_are_correct(self):
        response = self.client.get("/dashboard/")
        self.assertEqual(response.context["total_bugs"], [2, 0, 1])
        self.assertEqual(response.context["severity_counts"], [1, 0, 1, 1])
        self.assertEqual(response.context["assigned_counts"], [1, 2])

    def test_chart_data_is_valid_json(self):
        html = self.client.get("/dashboard/").content.decode()
        for attribute in ["data-bugs", "data-severity", "data-assigned"]:
            with self.subTest(attribute=attribute):
                value = re.search(rf'{attribute}="([^"]*)"', html).group(1)
                self.assertIsInstance(json.loads(value), list)


class LogoutTest(TestCase):
    def test_logout_with_POST_logs_user_out(self):
        self.client.force_login(make_user("alice", "Reporter"))
        response = self.client.post("/logout/")
        self.assertRedirects(response, "/")
        self.assertNotIn("_auth_user_id", self.client.session)

import os

from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import expect, sync_playwright

from bugs.models import BugReport, UserProfile

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

PASSWORD = "S3cret-pass-123"


class FunctionalTest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.set_default_timeout(10000)

    def tearDown(self):
        self.page.close()

    def create_user(self, username, role):
        user = User.objects.create_user(username=username, password=PASSWORD)
        UserProfile.objects.create(user=user, role=role)
        return user

    def log_in(self, username):
        self.page.goto(f"{self.live_server_url}/login/")
        self.page.fill("#id_username", username)
        self.page.fill("#id_password", PASSWORD)
        self.page.click("button[type=submit]")
        expect(self.page.get_by_role("heading", name="Bug Tracker Dashboard")).to_be_visible()


class NewDeveloperTest(FunctionalTest):
    def test_can_register_and_report_a_bug(self):
        # Dana is a developer. She opens the home page and goes to Register
        self.page.goto(self.live_server_url)
        expect(self.page.get_by_role("heading", name="Welcome to Bug Tracker Lite")).to_be_visible()
        self.page.click("text=Register")

        # She fills in the registration form and picks the Developer role
        self.page.fill("#id_username", "dana")
        self.page.fill("#id_email", "dana@example.com")
        self.page.fill("#id_password1", PASSWORD)
        self.page.fill("#id_password2", PASSWORD)
        self.page.select_option("#id_role", "Developer")
        self.page.click("button:has-text('Register')")

        # She is logged in and sees her name and role in the navbar
        expect(self.page.locator("nav")).to_contain_text("dana (Developer)")

        # She opens the Bug List and reports a new bug
        self.page.click("nav >> text=Bug List")
        self.page.click("text=+ Report New Bug")
        self.page.fill("#id_title", "Login button is grey")
        self.page.fill("#id_description", "It should be blue")
        self.page.select_option("#id_severity", "Medium")
        self.page.fill("#id_project", "Website")
        self.page.click("button:has-text('Save')")

        # The bug now appears in the table with her as reporter
        row = self.page.locator("tbody tr", has_text="Login button is grey")
        expect(row).to_contain_text("Website")
        expect(row).to_contain_text("dana")


class BugListFilterTest(FunctionalTest):
    def test_filter_dropdown_keeps_chosen_status(self):
        dev = self.create_user("dev", "Developer")
        BugReport.objects.create(
            title="Fixed bug", description="x", status="Resolved",
            severity="Low", project="Demo", reporter=dev,
        )
        self.log_in("dev")
        self.page.goto(f"{self.live_server_url}/bug_list/")

        # Dev filters the list by "Resolved"
        self.page.select_option("select[name=status]", "Resolved")
        self.page.click("button:has-text('Filter')")

        # The list is filtered correctly...
        expect(self.page.locator("tbody")).to_contain_text("Fixed bug")
        # ...and the dropdown should still show the chosen value
        # POSSIBLE BUG: template checks "selected_status" but the view sends "status_filter",
        # so the dropdown jumps back to "All Statuses"
        expect(self.page.locator("select[name=status]")).to_have_value("Resolved")


class ReporterPermissionTest(FunctionalTest):
    def test_reporter_cannot_edit_bug_by_typing_the_url(self):
        bob = self.create_user("bob", "Reporter")
        bug = BugReport.objects.create(
            title="Bob's bug", description="x", severity="Low",
            project="Demo", reporter=bob,
        )
        self.create_user("eve", "Reporter")
        self.log_in("eve")

        # Eve has no Edit button, but she types the edit URL directly
        self.page.goto(f"{self.live_server_url}/bug_update/{bug.id}/")

        # POSSIBLE BUG: bug_update has no role/owner check, so the edit form opens
        # and Eve can change another user's bug
        expect(self.page.locator("#id_title")).to_have_count(0)

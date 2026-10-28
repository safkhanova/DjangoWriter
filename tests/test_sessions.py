from django.conf import settings
from django.contrib.auth.models import Group, User
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from core.models import UserSession
from core.permissions import EDITOR_GROUP
from core.sessions import revoke_user_sessions


class SessionRevocationTests(TestCase):
    def setUp(self):
        self.editor = User.objects.create_user("e@x.az", "e@x.az", "pw", is_staff=True)
        self.editor.groups.add(Group.objects.get(name=EDITOR_GROUP))
        self.laptop, self.phone = Client(HTTP_USER_AGENT="Mozilla (Macintosh; Mac OS X) Chrome/120"), Client()
        self.laptop.force_login(self.editor)
        self.phone.force_login(self.editor)
        # force_login's fake request carries no headers: let the middleware track the
        # sessions from real requests instead, as happens after an emailotp login.
        UserSession.objects.all().delete()
        self.laptop.get(reverse("admin:index"))
        self.phone.get(reverse("admin:index"))

    def is_logged_in(self, client):
        return client.get(reverse("admin:index")).status_code == 200

    def test_remember_me_is_30_days(self):
        self.assertEqual(settings.EMAILOTP_REMEMBER_AGE, 30 * 24 * 3600)

    def test_sessions_are_tracked(self):
        self.assertEqual(UserSession.objects.filter(user=self.editor).count(), 2)
        devices = {s.device for s in UserSession.objects.filter(user=self.editor)}
        self.assertIn("Mac · Chrome", devices)

    def test_revoke_other_devices_keeps_current(self):
        response = self.laptop.post(reverse("admin:core_usersession_revoke_other_devices"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.is_logged_in(self.laptop))
        self.assertFalse(self.is_logged_in(self.phone))
        self.assertEqual(UserSession.objects.filter(user=self.editor).count(), 1)

    def test_editor_sees_only_own_sessions(self):
        other = User.objects.create_user("o@x.az", "o@x.az", "pw", is_staff=True)
        c = Client()
        c.force_login(other)
        c.get(reverse("admin:index"))
        page = self.laptop.get(reverse("admin:core_usersession_changelist"))
        self.assertEqual(page.status_code, 200)
        self.assertEqual(len(page.context["cl"].result_list), 2)

    def test_superuser_revokes_user_everywhere(self):
        admin = User.objects.create_superuser("a@x.az", "a@x.az", "pw")
        c = Client()
        c.force_login(admin)
        c.post(reverse("admin:auth_user_revoke_sessions_detail", args=[self.editor.pk]))
        self.assertFalse(self.is_logged_in(self.laptop))
        self.assertFalse(self.is_logged_in(self.phone))
        self.assertTrue(self.is_logged_in(c))

    def test_untracked_sessions_are_also_revoked(self):
        UserSession.objects.all().delete()  # e.g. sessions older than the tracking feature
        self.assertEqual(revoke_user_sessions(self.editor), 2)
        self.assertFalse(self.is_logged_in(self.phone))

    def test_management_command(self):
        call_command("revoke_sessions", "e@x.az", stdout=open("/dev/null", "w"))
        self.assertFalse(self.is_logged_in(self.laptop))
        call_command("revoke_sessions", "--all", stdout=open("/dev/null", "w"))
        self.assertFalse(Session.objects.exists())

    def test_logout_removes_tracking_row(self):
        self.phone.post(reverse("admin:logout"))
        self.assertEqual(UserSession.objects.filter(user=self.editor).count(), 1)

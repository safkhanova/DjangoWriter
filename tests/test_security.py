from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from content.models import Article, ArticleBlock, Section, is_safe_link
from core.models import ContactTopic, Hero, SiteSettings, UserSession
from core.permissions import EDITOR_GROUP
from emailotp.models import AuthEvent
from newsletter.admin import csv_safe
from newsletter.models import Subscriber


class AdminCsrfTests(TestCase):
    """State-changing admin actions must not run on a plain GET (CSRF via link/img)."""

    def setUp(self):
        self.admin = User.objects.create_superuser("a@x.az", "a@x.az", "pw")
        self.client.force_login(self.admin)

    def test_hero_activation_needs_post(self):
        draft = Hero.objects.create(name="d")
        url = reverse("admin:core_hero_activate_detail", args=[draft.pk])
        response = self.client.get(url)
        self.assertContains(response, "csrfmiddlewaretoken")
        draft.refresh_from_db()
        self.assertFalse(draft.is_active)
        self.client.post(url)
        draft.refresh_from_db()
        self.assertTrue(draft.is_active)

    def test_revoke_sessions_needs_post(self):
        victim = User.objects.create_user("v@x.az", "v@x.az", "pw", is_staff=True)
        other = self.client_class()
        other.force_login(victim)
        other.get(reverse("admin:index"))
        url = reverse("admin:auth_user_revoke_sessions_detail", args=[victim.pk])
        self.client.get(url)
        self.assertEqual(other.get(reverse("admin:index")).status_code, 200)
        self.client.post(url)
        self.assertNotEqual(other.get(reverse("admin:index")).status_code, 200)

    def test_revoke_other_devices_needs_post(self):
        url = reverse("admin:core_usersession_revoke_other_devices")
        second = self.client_class()
        second.force_login(self.admin)
        second.get(reverse("admin:index"))
        self.client.get(url)
        self.assertEqual(second.get(reverse("admin:index")).status_code, 200)
        self.client.post(url)
        self.assertNotEqual(second.get(reverse("admin:index")).status_code, 200)

    def test_csrf_enforced(self):
        csrf_client = self.client_class(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        draft = Hero.objects.create(name="d")
        response = csrf_client.post(reverse("admin:core_hero_activate_detail", args=[draft.pk]))
        self.assertEqual(response.status_code, 403)


class PasswordBruteForceTests(TestCase):
    def setUp(self):
        User.objects.create_user("s@x.az", "s@x.az", "right-password", is_staff=True)

    def start(self, client):
        session = client.session
        session.update({"emailotp_email": "s@x.az", "emailotp_stage": "password", "emailotp_flow": "login"})
        session.save()

    def test_account_locked_after_ten_failures(self):
        self.start(self.client)
        for i in range(10):
            self.client.post("/login/password/", {"password": f"wrong{i}"})
        # even the right password is refused for the rest of the hour
        response = self.client.post("/login/password/", {"password": "right-password"})
        self.assertRedirects(response, "/login/password/", fetch_redirect_response=False)
        self.assertTrue(AuthEvent.objects.filter(kind=AuthEvent.THROTTLED).exists())

    def test_correct_password_still_works_normally(self):
        self.start(self.client)
        response = self.client.post("/login/password/", {"password": "right-password"})
        self.assertRedirects(response, reverse("emailotp:login_verify"), fetch_redirect_response=False)


class UploadTests(TestCase):
    def test_logo_rejects_html_and_scripted_svg(self):
        site = SiteSettings.load()
        for name, body in [("x.html", b"<script>alert(1)</script>"),
                           ("x.svg", b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>')]:
            site.logo = SimpleUploadedFile(name, body)
            with self.assertRaises(ValidationError, msg=name):
                site.full_clean()

    def test_logo_accepts_clean_svg(self):
        site = SiteSettings.load()
        site.logo = SimpleUploadedFile("x.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h1v1z"/></svg>')
        site.full_clean()

    def test_block_file_rejects_html(self):
        art = Article.objects.create(section=Section.objects.first(), title="x")
        block = ArticleBlock(article=art, type="pdf", file=SimpleUploadedFile("x.html", b"<script>"))
        with self.assertRaises(ValidationError):
            block.full_clean()


class XssTests(TestCase):
    def test_rich_text_sanitized_and_rendered(self):
        section = Section.objects.get(slug="edebiyyat")
        art = Article.objects.create(section=section, title="x", status="published")
        ArticleBlock.objects.create(article=art, type="text",
                                    text='<p onclick="x()">ok<script>alert(1)</script><img src=x onerror=alert(1)></p>')
        html = self.client.get(art.get_absolute_url()).content.decode()
        self.assertIn("ok", html)
        for bad in ("<script>alert", "onerror", "onclick"):
            self.assertNotIn(bad, html)

    def test_title_escaped(self):
        section = Section.objects.get(slug="edebiyyat")
        Article.objects.create(section=section, title="<script>alert(1)</script>", status="published")
        self.assertNotIn("<script>alert(1)</script>", self.client.get("/").content.decode())

    def test_safe_links(self):
        for url in ("javascript:alert(1)", "//evil.example", "data:text/html,x", "vbscript:x"):
            self.assertFalse(is_safe_link(url), url)
        for url in ("https://x.az", "/elaqe/", "#elaqe", "mailto:a@x.az"):
            self.assertTrue(is_safe_link(url), url)

    def test_editor_cannot_inject_analytics_script(self):
        editor = User.objects.create_user("e@x.az", "e@x.az", "pw", is_staff=True)
        editor.groups.add(Group.objects.get(name=EDITOR_GROUP))
        self.client.force_login(editor)
        form = self.client.get(reverse("admin:core_sitesettings_change", args=[1])).context["adminform"].form
        self.assertNotIn("analytics_snippet", form.fields)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PublicFormTests(TestCase):
    def test_newline_in_name_cannot_break_email_headers(self):
        site = SiteSettings.load()
        site.notification_email = "owner@x.az"
        site.save()
        self.client.post(reverse("core:contact"), {
            "name": "Eve\r\nBcc: victim@x.az", "email": "e@x.az",
            "topic": ContactTopic.objects.first().pk, "message": "hi",
        })
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("\n", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].bcc, [])

    def test_message_length_limited(self):
        response = self.client.post(reverse("core:contact"), {
            "name": "A", "email": "a@x.az", "message": "x" * 5001,
        })
        self.assertEqual(response.status_code, 400)

    def test_csv_formula_neutralised(self):
        self.assertEqual(csv_safe("=HYPERLINK(1)"), "'=HYPERLINK(1)")
        self.assertEqual(csv_safe("Aysel"), "Aysel")

    def test_unknown_token_404(self):
        import uuid

        self.assertEqual(self.client.get(reverse("newsletter:manage", args=[uuid.uuid4()])).status_code, 404)
        self.assertFalse(Subscriber.objects.exists())


class HeaderTests(TestCase):
    def test_public_pages_have_csp(self):
        response = self.client.get("/")
        csp = response["Content-Security-Policy"]
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertNotIn("'unsafe-inline' https://fonts.gstatic", csp)
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertIn("Permissions-Policy", response)

    def test_admin_has_no_public_csp(self):
        admin = User.objects.create_superuser("a@x.az", "a@x.az", "pw")
        self.client.force_login(admin)
        self.assertNotIn("Content-Security-Policy", self.client.get(reverse("admin:index")))

    def test_draft_not_leaked(self):
        section = Section.objects.get(slug="edebiyyat")
        Article.objects.create(section=section, title="GİZLİ QARALAMA")
        for url in ("/", section.get_absolute_url(), "/sitemap.xml"):
            self.assertNotContains(self.client.get(url), "GİZLİ QARALAMA")
        self.assertFalse(UserSession.objects.exists())

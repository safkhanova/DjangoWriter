from datetime import timedelta
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from content.models import Article, ArticleBlock, Section, youtube_id
from core.models import ContactMessage, ContactTopic, Hero, SiteSettings
from core.permissions import EDITOR_GROUP
from core.utils import az_slugify, sanitize_html
from newsletter.models import NewsletterIssue, OutgoingEmail, Subscriber
from newsletter.services import queue_article_newsletter, send_queued


def make_article(section, title="Yazı", **kw):
    kw.setdefault("status", Article.Status.PUBLISHED)
    kw.setdefault("publish_at", timezone.now() - timedelta(hours=1))
    return Article.objects.create(section=section, title=title, **kw)


def jpeg(size=(3000, 2000)):
    buf = BytesIO()
    Image.new("RGB", size, (10, 120, 90)).save(buf, "JPEG")
    return SimpleUploadedFile("photo.jpg", buf.getvalue(), "image/jpeg")


class UtilsTests(TestCase):
    def test_az_slug(self):
        self.assertEqual(az_slugify("Şeirin adı — Ədəbiyyat"), "sheirin-adi-edebiyyat")
        self.assertEqual(az_slugify("Koçluq"), "kochluq")

    def test_youtube_id(self):
        for url in [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
        ]:
            self.assertEqual(youtube_id(url), "dQw4w9WgXcQ", url)
        self.assertIsNone(youtube_id("https://vimeo.com/123"))

    def test_sanitize_strips_scripts(self):
        html = sanitize_html('<div onclick="x()">ok<script>alert(1)</script><a href="javascript:x">l</a></div>')
        self.assertNotIn("script", html)
        self.assertNotIn("onclick", html)
        self.assertNotIn("javascript", html)


class SeedTests(TestCase):
    def test_seed_migration(self):
        self.assertEqual(
            list(Section.objects.values_list("slug", flat=True)),
            ["edebiyyat", "pr", "media-arxivi", "kocluq"],
        )
        self.assertTrue(Hero.objects.filter(is_active=True).exists())
        self.assertTrue(Group.objects.get(name=EDITOR_GROUP).permissions.filter(codename="change_article").exists())


class HeroTests(TestCase):
    def test_only_one_active(self):
        first = Hero.objects.get(is_active=True)
        second = Hero.objects.create(name="Yeni", is_active=True)
        first.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertEqual(Hero.objects.filter(is_active=True).get(), second)

    def test_staff_can_preview_draft_hero(self):
        draft = Hero.objects.create(name="Qaralama", title_line_1="QARALAMA BAŞLIQ")
        url = reverse("core:home") + f"?hero={draft.pk}"
        self.assertNotContains(self.client.get(url), "QARALAMA BAŞLIQ")
        staff = User.objects.create_user("s@x.az", "s@x.az", "pw", is_staff=True)
        self.client.force_login(staff)
        self.assertContains(self.client.get(url), "QARALAMA BAŞLIQ")


class VisibilityTests(TestCase):
    def setUp(self):
        self.section = Section.objects.get(slug="edebiyyat")
        self.staff = User.objects.create_user("s@x.az", "s@x.az", "pw", is_staff=True)

    def get(self, article):
        return self.client.get(article.get_absolute_url())

    def test_draft_only_for_staff(self):
        art = make_article(self.section, "Gizli yazı", status=Article.Status.DRAFT)
        self.assertEqual(self.get(art).status_code, 404)
        self.assertNotContains(self.client.get("/"), "Gizli yazı")
        self.client.force_login(self.staff)
        self.assertContains(self.get(art), "Qaralama")
        self.assertContains(self.client.get("/"), "Gizli yazı")

    def test_scheduled_article(self):
        art = make_article(self.section, publish_at=timezone.now() + timedelta(days=1))
        self.assertEqual(self.get(art).status_code, 404)
        self.assertTrue(art.is_scheduled)

    def test_hidden_section_hides_articles(self):
        art = make_article(self.section)
        self.section.is_visible = False
        self.section.save()
        self.assertEqual(self.get(art).status_code, 404)
        self.assertEqual(self.client.get(self.section.get_absolute_url()).status_code, 404)
        self.client.force_login(self.staff)
        self.assertEqual(self.get(art).status_code, 200)

    def test_hidden_block(self):
        art = make_article(self.section)
        ArticleBlock.objects.create(article=art, type="text", text="<div>GÖRÜNƏN</div>")
        ArticleBlock.objects.create(article=art, type="text", text="<div>GİZLİ</div>", is_visible=False)
        response = self.get(art)
        self.assertContains(response, "GÖRÜNƏN")
        self.assertNotContains(response, "GİZLİ")
        self.client.force_login(self.staff)
        self.assertContains(self.get(art), "GİZLİ")

    def test_homepage_order_featured_then_pinned(self):
        old_featured = make_article(self.section, "Seçilmiş", is_featured=True,
                                    publish_at=timezone.now() - timedelta(days=30))
        make_article(self.section, "Yeni")
        pinned = make_article(self.section, "Sabit", is_pinned=True, publish_at=timezone.now() - timedelta(days=10))
        ordered = list(Article.objects.filter(section=self.section).homepage_order())
        self.assertEqual(ordered[:2], [old_featured, pinned])

    def test_external_link_mode(self):
        media = Section.objects.get(slug="media-arxivi")
        art = make_article(media, link_mode=Article.LinkMode.EXTERNAL, external_url="https://qezet.az/x")
        self.assertEqual(art.href, "https://qezet.az/x")
        self.assertContains(self.client.get("/"), 'href="https://qezet.az/x"')


class BlockValidationTests(TestCase):
    def setUp(self):
        self.art = make_article(Section.objects.first())

    def test_text_image_requires_side_position_and_max_width(self):
        block = ArticleBlock(article=self.art, type="text_image", text="<div>x</div>", image=jpeg(),
                             image_position="center", image_width=90)
        with self.assertRaises(ValidationError) as ctx:
            block.full_clean()
        self.assertIn("image_position", ctx.exception.message_dict)
        self.assertIn("image_width", ctx.exception.message_dict)

    def test_unsafe_button_link_rejected(self):
        block = ArticleBlock(article=self.art, type="button", button_label="x", button_url="javascript:alert(1)")
        with self.assertRaises(ValidationError):
            block.full_clean()

    def test_uploaded_image_converted_to_webp_and_resized(self):
        block = ArticleBlock.objects.create(article=self.art, type="image", image=jpeg())
        self.assertTrue(block.image.name.endswith(".webp"))
        with Image.open(block.image.path) as img:
            self.assertLessEqual(max(img.size), 2400)
        block.image.delete(save=False)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NewsletterTests(TestCase):
    def setUp(self):
        self.lit = Section.objects.get(slug="edebiyyat")
        self.pr = Section.objects.get(slug="pr")

    def subscribe(self, email, sections):
        return self.client.post(reverse("newsletter:subscribe"), {"email": email, "sections": [s.pk for s in sections]})

    def test_double_opt_in(self):
        self.subscribe("a@x.az", [self.lit])
        sub = Subscriber.objects.get(email="a@x.az")
        self.assertFalse(sub.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(str(sub.token), mail.outbox[0].body)
        self.client.get(reverse("newsletter:confirm", args=[sub.token]))
        sub.refresh_from_db()
        self.assertTrue(sub.is_active)

    def test_only_interested_subscribers_receive(self):
        Subscriber.objects.create(email="lit@x.az", is_confirmed=True).sections.add(self.lit)
        Subscriber.objects.create(email="pr@x.az", is_confirmed=True).sections.add(self.pr)
        Subscriber.objects.create(email="all@x.az", is_confirmed=True)  # no sections = everything
        Subscriber.objects.create(email="pending@x.az")  # not confirmed
        art = make_article(self.lit, excerpt="Xülasə")
        issue = queue_article_newsletter(art)
        self.assertEqual(
            set(issue.emails.values_list("to_email", flat=True)), {"lit@x.az", "all@x.az"},
        )
        self.assertEqual(send_queued(), (2, 0))
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("List-Unsubscribe", mail.outbox[0].extra_headers)
        with self.assertRaises(ValueError):
            queue_article_newsletter(art)  # never twice

    def test_draft_cannot_be_sent(self):
        art = make_article(self.lit, status=Article.Status.DRAFT)
        with self.assertRaises(ValueError):
            queue_article_newsletter(art)
        self.assertFalse(NewsletterIssue.objects.exists())

    def test_one_click_unsubscribe(self):
        sub = Subscriber.objects.create(email="u@x.az", is_confirmed=True)
        self.client.post(reverse("newsletter:one_click_unsubscribe", args=[sub.token]))
        sub.refresh_from_db()
        self.assertFalse(sub.is_active)

    def test_honeypot(self):
        self.client.post(reverse("newsletter:subscribe"), {"email": "bot@x.az", "website": "spam"})
        self.assertFalse(Subscriber.objects.exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ContactTests(TestCase):
    def test_message_saved_and_notified(self):
        site = SiteSettings.load()
        site.notification_email = "owner@x.az"
        site.save()
        topic = ContactTopic.objects.first()
        response = self.client.post(reverse("core:contact"), {
            "name": "Aysel", "email": "aysel@x.az", "topic": topic.pk, "message": "Salam",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContactMessage.objects.get().name, "Aysel")
        self.assertEqual(mail.outbox[0].to, ["owner@x.az"])
        self.assertEqual(mail.outbox[0].reply_to, ["aysel@x.az"])

    def test_invalid_form(self):
        response = self.client.post(reverse("core:contact"), {"name": "", "email": "bad", "message": ""})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ContactMessage.objects.exists())


class AdminTests(TestCase):
    def test_admin_login_goes_through_email_otp(self):
        response = self.client.get(reverse("admin:login"))
        self.assertRedirects(response, reverse("emailotp:login") + "?next=" + reverse("admin:login"),
                             fetch_redirect_response=False)

    def test_registration_disabled(self):
        self.assertRedirects(self.client.get("/register/"), reverse("emailotp:login"), fetch_redirect_response=False)

    def test_admin_pages_render_for_superuser(self):
        admin = User.objects.create_superuser("a@x.az", "a@x.az", "pw")
        self.client.force_login(admin)
        art = make_article(Section.objects.first())
        for url in [
            reverse("admin:index"),
            reverse("admin:content_article_changelist"),
            reverse("admin:content_article_add"),
            reverse("admin:content_article_change", args=[art.pk]),
            reverse("admin:content_article_send_newsletter", args=[art.pk]),
            reverse("admin:content_section_changelist"),
            reverse("admin:core_hero_changelist"),
            reverse("admin:core_sitesettings_change", args=[1]),
            reverse("admin:core_contactmessage_changelist"),
            reverse("admin:newsletter_subscriber_changelist"),
        ]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_editor_sees_content_not_users(self):
        editor = User.objects.create_user("e@x.az", "e@x.az", "pw", is_staff=True)
        editor.groups.add(Group.objects.get(name=EDITOR_GROUP))
        self.client.force_login(editor)
        self.assertEqual(self.client.get(reverse("admin:content_article_add")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:auth_user_changelist")).status_code, 403)


class AuthorshipTests(TestCase):
    def setUp(self):
        self.media = Section.objects.get(slug="media-arxivi")
        self.own = make_article(self.media, "Öz yazım")
        self.about = make_article(self.media, "Onun haqqında", authorship=Article.Authorship.ABOUT,
                                  original_author="Fatimə Mövlamlı")

    def test_own_text_cannot_have_other_author(self):
        art = Article(section=self.media, title="x", authorship=Article.Authorship.OWN, original_author="Başqası")
        with self.assertRaises(ValidationError) as ctx:
            art.full_clean()
        self.assertIn("original_author", ctx.exception.message_dict)

    def test_badge_only_for_texts_not_by_her(self):
        self.assertEqual(self.own.authorship_label, "")
        self.assertEqual(self.about.authorship_label, "Haqqımda")
        response = self.client.get(self.media.get_absolute_url())
        self.assertContains(response, 'authorship-badge authorship-about', count=1)
        self.assertContains(response, "Fatimə Mövlamlı")

    def test_section_filter_by_authorship(self):
        response = self.client.get(self.media.get_absolute_url() + "?kim=about")
        self.assertContains(response, "Onun haqqında")
        self.assertNotContains(response, "Öz yazım")
        self.assertEqual([v for v, _ in response.context["authorship_choices"]], ["own", "about"])

    def test_mention(self):
        mention = make_article(self.media, "Qaliblərin siyahısı", authorship=Article.Authorship.MENTION)
        self.assertEqual(mention.authorship_label, "Adım çəkilir")
        mention.full_clean()  # a mention may carry the journalist's name too
        response = self.client.get(self.media.get_absolute_url() + "?kim=mention")
        self.assertContains(response, "Qaliblərin siyahısı")
        self.assertNotContains(response, "Onun haqqında")
        self.assertContains(response, "Adımın çəkildiyi yazılar")

    def test_filter_hidden_when_section_has_one_kind(self):
        response = self.client.get(Section.objects.get(slug="edebiyyat").get_absolute_url())
        self.assertNotContains(response, "?kim=")


class ArticleCategoryChoiceTests(TestCase):
    def setUp(self):
        from content.admin import ArticleAdminForm

        self.Form = ArticleAdminForm
        self.lit = Section.objects.get(slug="edebiyyat")
        self.coaching = Section.objects.get(slug="kocluq")

    def test_choices_limited_to_section(self):
        art = make_article(self.lit)
        field = self.Form(instance=art).fields["category"]
        self.assertEqual(set(field.queryset), set(self.lit.categories.all()))
        self.assertEqual(field.label_from_instance(self.lit.categories.first()), self.lit.categories.first().name)

    def test_no_section_no_choices(self):
        self.assertFalse(self.Form().fields["category"].queryset.exists())

    def test_mismatched_category_rejected_on_post(self):
        video = self.coaching.categories.get(name="Video")
        form = self.Form(data={"section": self.lit.pk, "category": video.pk})
        form.is_valid()
        self.assertIn("category", form.errors)

    def test_admin_page_ships_section_map(self):
        admin = User.objects.create_superuser("a@x.az", "a@x.az", "pw")
        self.client.force_login(admin)
        response = self.client.get(reverse("admin:content_article_add"))
        self.assertContains(response, 'id="categories-by-section"')
        self.assertContains(response, "article_form.js")

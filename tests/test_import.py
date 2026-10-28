import json
import tempfile
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import TestCase

from content.models import Article, Category, Section
from core.models import ContactTopic, Hero, SiteSettings

EXAMPLE = settings.BASE_DIR / "instance.example"


class ExampleInstanceTests(TestCase):
    """instance.example/ is what a new site starts from: it must always load."""

    def test_example_seed_loads(self):
        call_command("setup_site", "--seed", str(EXAMPLE / "seed.json"), stdout=StringIO())
        self.assertTrue(Section.objects.filter(slug="meqaleler", layout="card_grid").exists())
        video = Section.objects.get(slug="video")
        self.assertEqual(video.cta_topic, ContactTopic.objects.get(name="Görüş / təqdimat"))
        self.assertEqual(list(video.categories.values_list("name", flat=True)), ["Video", "Yazı"])

    def test_seed_rerun_keeps_admin_edits(self):
        call_command("setup_site", "--seed", str(EXAMPLE / "seed.json"), stdout=StringIO())
        section = Section.objects.get(slug="meqaleler")
        section.title = "Redaktə olunub"
        section.save()
        call_command("setup_site", "--seed", str(EXAMPLE / "seed.json"), stdout=StringIO())
        self.assertEqual(Section.objects.get(slug="meqaleler").title, "Redaktə olunub")

    def test_hero_not_activated_when_one_is_live(self):
        live = Hero.objects.get(is_active=True)  # from the test seed
        call_command("setup_site", "--seed", str(EXAMPLE / "seed.json"), stdout=StringIO())
        live.refresh_from_db()
        self.assertTrue(live.is_active)
        self.assertEqual(Hero.objects.filter(is_active=True).count(), 1)

    def test_example_content_imports_with_text(self):
        call_command("setup_site", "--seed", str(EXAMPLE / "seed.json"), stdout=StringIO())
        call_command("import_content", str(EXAMPLE / "content" / "example.json"), "--publish", stdout=StringIO())
        story = Article.objects.get(title="Nümunə hekayə")
        self.assertTrue(story.is_public)
        self.assertEqual(
            [b.type for b in story.blocks.all()], ["text", "heading", "quote", "divider", "text"],
        )
        interview = Article.objects.get(title="Nümunə müsahibə")
        self.assertEqual((interview.authorship, interview.original_author), ("interview", "Jurnalistin adı"))


class ImportContentTests(TestCase):
    def write(self, tmp, data):
        path = Path(tmp, "data.json")
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def test_idempotent_and_drafts_by_default(self):
        data = {"site": {"site_name": "Yeni Ad"}, "articles": [
            {"section": "media-arxivi", "category": "Mükafat", "title": "A", "authorship": "mention"},
            {"section": "edebiyyat", "category": "Hekayə", "title": "B", "force_draft": True},
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, data)
            call_command("import_content", path, stdout=StringIO())
            call_command("import_content", path, stdout=StringIO())
        self.assertEqual(Article.objects.count(), 2)
        self.assertFalse(Article.objects.public().exists())
        self.assertTrue(Category.objects.filter(section__slug="media-arxivi", name="Mükafat").exists())
        self.assertEqual(SiteSettings.load().site_name, "Test Müəllif")  # not a placeholder: kept

    def test_publish_flag_respects_force_draft(self):
        data = {"articles": [
            {"section": "edebiyyat", "title": "Açıq"},
            {"section": "edebiyyat", "title": "Gizli", "force_draft": True},
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            call_command("import_content", self.write(tmp, data), "--publish", stdout=StringIO())
        self.assertTrue(Article.objects.public().filter(title="Açıq").exists())
        self.assertEqual(Article.objects.get(title="Gizli").status, Article.Status.DRAFT)

    def test_dry_run_saves_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            call_command("import_content", self.write(tmp, {"articles": [{"section": "pr", "title": "X"}]}),
                         "--dry-run", stdout=StringIO())
        self.assertFalse(Article.objects.exists())


class TextImportTests(TestCase):
    def test_parse_text(self):
        from content.management.commands.import_content import parse_text

        blocks = parse_text("Birinci abzas\nikinci sətir\n\n  \nİkinci <b>abzas</b>\n\n## Ara başlıq\n\n> Sitat\n\n***\n\nSon")
        self.assertEqual([b["type"] for b in blocks], ["text", "heading", "quote", "divider", "text"])
        self.assertEqual(blocks[0]["text"], "<p>Birinci abzas<br>ikinci sətir</p><p>İkinci &lt;b&gt;abzas&lt;/b&gt;</p>")

    def test_body_from_file_page_mode_and_source_box(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {"articles": [{
                "section": "edebiyyat", "title": "Uçuş", "external_url": "https://kulis.az/x",
                "source_name": "Kulis.az", "publish_at": "2026-04-10T12:00:00+04:00",
            }]}
            Path(tmp, "data.json").write_text(json.dumps(data), encoding="utf-8")
            Path(tmp, "texts").mkdir()
            Path(tmp, "texts", "uchush.md").write_text("Ağ ördək.\n\nGeri qayıtdı.", encoding="utf-8")
            call_command("import_content", f"{tmp}/data.json", "--publish", stdout=StringIO())
            article = Article.objects.get(title="Uçuş")
            self.assertEqual(article.link_mode, Article.LinkMode.PAGE)
            self.assertEqual(article.blocks.count(), 1)

            article.blocks.update(text="<p>Redaktə olunub</p>")
            call_command("import_content", f"{tmp}/data.json", "--publish", stdout=StringIO())
            self.assertEqual(article.blocks.get().text, "<p>Redaktə olunub</p>")
            call_command("import_content", f"{tmp}/data.json", "--publish", "--replace-texts", stdout=StringIO())
            self.assertIn("Ağ ördək", article.blocks.get().text)

        response = self.client.get(article.get_absolute_url())
        self.assertContains(response, "Ağ ördək")
        self.assertContains(response, "İlk dəfə dərc olunub")
        self.assertContains(response, 'href="https://kulis.az/x"')
        self.assertEqual(article.href, article.get_absolute_url())


class MediaImportTests(TestCase):
    def test_cover_image_copied_from_json_folder(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as media:
            data = {"articles": [{"section": "edebiyyat", "title": "Şəkilli", "cover_image": "portraits/p.webp"}]}
            Path(tmp, "data.json").write_text(json.dumps(data), encoding="utf-8")
            Path(tmp, "media", "portraits").mkdir(parents=True)
            Path(tmp, "media", "portraits", "p.webp").write_bytes(b"RIFF0000WEBP")
            with self.settings(MEDIA_ROOT=media):
                call_command("import_content", f"{tmp}/data.json", stdout=StringIO())
                self.assertEqual(Path(media, "portraits", "p.webp").read_bytes(), b"RIFF0000WEBP")
                self.assertEqual(Article.objects.get(title="Şəkilli").cover_image.name, "portraits/p.webp")

    def test_media_path_outside_folder_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = {"articles": [{"section": "edebiyyat", "title": "X", "cover_image": "../secret.webp"}]}
            Path(tmp, "data.json").write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(CommandError):
                call_command("import_content", f"{tmp}/data.json", stdout=StringIO())

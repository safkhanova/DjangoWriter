"""
Import a site's structure and content from a JSON file.

Used for the initial setup of a new site (instance/seed.json, see instance.example/)
and for bulk content imports (instance/content/*.json). All keys are optional:

  site            SiteSettings fields
  contact_topics  ["Əməkdaşlıq", ...] (or {"name", "is_visible"})
  social_links    [{"name", "icon", "url"}]
  sections        [{"slug", "title", "layout", "theme", ..., "categories": [...], "cta_topic": "<topic name>"}]
  hero            {"name", "title_line_1", ..., "tags": [...], "active": true}
  articles        [{"section", "category", "title", ...}]

Idempotent: running it twice updates the same rows instead of duplicating them.
Articles are matched by (section, slug of title). Imported articles are drafts unless
--publish is given; entries with "force_draft" always stay drafts.
Existing site settings and sections are only filled where still empty or at the
placeholder default, unless --overwrite is given, so changes made in the admin
survive a re-run. The hero becomes active only if the site has no active hero yet
(and "active": true); otherwise it is stored as an inactive version.

Articles become pages on this site. The body is read from a text file, if one exists:
<texts dir>/<slug>.md or .txt (or the item's "text_file"). Blank lines separate
paragraphs; a line starting with "## " is a subheading, one starting with "> " a quote.
The original publication (external_url) is shown under the text as the source.
Existing bodies are kept unless --replace-texts is given, so edits made in the
admin are never overwritten by accident.
"""

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils.html import escape

from content.models import Article, ArticleBlock, Category, Section
from core.models import ContactTopic, Hero, HeroTag, SiteSettings, SocialLink
from core.utils import az_slugify

PLACEHOLDERS = {"", "Adınız Soyadınız"}
ARTICLE_FIELDS = (
    "excerpt", "source_name", "source_year", "external_url", "is_featured", "is_pinned",
    "authorship", "original_author",
)


class Command(BaseCommand):
    help = "Import site settings, contact topics, social links, sections, hero and articles from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--publish", action="store_true", help="Publish imported articles (default: drafts).")
        parser.add_argument("--overwrite", action="store_true", help="Overwrite non-empty site/section fields.")
        parser.add_argument("--dry-run", action="store_true", help="Show what would change, then roll back.")
        parser.add_argument("--texts", default=None, help="Folder with article texts (default: <json dir>/texts).")
        parser.add_argument("--replace-texts", action="store_true", help="Replace existing article bodies.")

    def handle(self, path, publish, overwrite, dry_run, texts, replace_texts, **options):
        file = Path(path)
        if not file.exists():
            raise CommandError(f"File not found: {file}")
        data = json.loads(file.read_text(encoding="utf-8"))
        self.publish, self.overwrite, self.replace_texts = publish, overwrite, replace_texts
        self.texts_dir = Path(texts) if texts else file.parent / "texts"

        with transaction.atomic():
            self.import_site(data.get("site", {}))
            self.import_topics(data.get("contact_topics", []))
            self.import_social(data.get("social_links", []))
            self.import_sections(data.get("sections", []))
            self.import_hero(data.get("hero"))
            for item in data.get("articles", []):
                self.import_article(item)
            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run: nothing was saved."))

    def log(self, msg):
        self.stdout.write(f"  {msg}")

    def import_site(self, values):
        site = SiteSettings.load()
        changed = []
        for field, value in values.items():
            current = getattr(site, field)
            untouched = str(current or "").strip() in PLACEHOLDERS or current == site._meta.get_field(field).get_default()
            if self.overwrite or untouched:
                setattr(site, field, value)
                changed.append(field)
        if changed:
            site.save()
        self.log(f"site settings: {', '.join(changed) or 'unchanged'}")

    def import_topics(self, items):
        for order, item in enumerate(items):
            item = {"name": item} if isinstance(item, str) else item
            _, created = ContactTopic.objects.get_or_create(
                name=item["name"], defaults={"order": order, "is_visible": item.get("is_visible", True)},
            )
            if created:
                self.log(f"+ contact topic «{item['name']}»")

    def import_social(self, items):
        for order, item in enumerate(items):
            _, created = SocialLink.objects.get_or_create(
                url=item["url"], defaults={"name": item["name"], "icon": item.get("icon", "website"), "order": order},
            )
            if created:
                self.log(f"+ social link {item['name']}")

    def import_hero(self, values):
        if not values:
            return
        values = dict(values)
        tags = values.pop("tags", [])
        wants_active = values.pop("active", False)
        hero, created = Hero.objects.get_or_create(name=values["name"])
        if created or self.overwrite:
            for field, value in values.items():
                setattr(hero, field, value)
            hero.is_active = hero.is_active or (wants_active and not Hero.objects.filter(is_active=True).exists())
            hero.save()
            hero.tags.all().delete()
            HeroTag.objects.bulk_create(HeroTag(hero=hero, label=label, order=i) for i, label in enumerate(tags))
        state = "active" if hero.is_active else "inactive (activate it in the admin)"
        self.log(f"hero «{hero.name}»: {'created' if created else 'kept'}, {state}")

    def import_sections(self, items):
        if isinstance(items, dict):  # older format: {"slug": {field: value}}
            items = [{"slug": slug, **fields} for slug, fields in items.items()]
        for order, item in enumerate(items):
            item = dict(item)
            categories = item.pop("categories", [])
            topic_name = item.pop("cta_topic", None)
            section = Section.objects.filter(slug=item["slug"]).first()
            created = section is None
            if created:
                if "title" not in item:
                    self.stderr.write(f"  section {item['slug']!r} not found and has no title, skipped")
                    continue
                section = Section(order=item.pop("order", order))
            for field, value in item.items():
                if created or self.overwrite or not getattr(section, field):
                    setattr(section, field, value)
            if topic_name and (created or self.overwrite or not section.cta_topic_id):
                section.cta_topic = ContactTopic.objects.filter(name=topic_name).first()
            section.full_clean(exclude=["cta_topic"])
            section.save()
            for i, name in enumerate(categories):
                Category.objects.get_or_create(section=section, slug=az_slugify(name), defaults={"name": name, "order": i})
            self.log(f"{'+' if created else '~'} section {section.slug} ({len(categories)} types)")

    def import_article(self, item):
        section = Section.objects.filter(slug=item["section"]).first()
        if section is None:
            self.stderr.write(f"  section {item['section']!r} not found, skipped «{item['title']}»")
            return
        category = None
        if item.get("category"):
            category, _ = Category.objects.get_or_create(
                section=section, slug=az_slugify(item["category"]), defaults={"name": item["category"]},
            )
        slug = az_slugify(item["title"], 120)
        article = Article.objects.filter(section=section, slug=slug).first()
        created = article is None
        if created:
            article = Article(section=section, slug=slug, title=item["title"])

        article.category = category
        for field in ARTICLE_FIELDS:
            if field in item:
                setattr(article, field, item[field])
        if item.get("publish_at"):
            article.publish_at = parse_datetime(item["publish_at"])
        article.link_mode = item.get("link_mode", Article.LinkMode.PAGE)
        if item.get("force_draft") or not self.publish:
            article.status = Article.Status.DRAFT
        else:
            article.status = Article.Status.PUBLISHED
        article.full_clean(exclude=["slug"])
        article.save()
        body = self.import_body(article, item)
        note = f" — {item['note']}" if item.get("note") else ""
        self.log(f"{'+' if created else '~'} [{section.slug}] {article.title} ({article.get_status_display()}, {body}){note}")

    def find_text(self, article, item) -> Path | None:
        candidates = [self.texts_dir / item["text_file"]] if item.get("text_file") else [
            self.texts_dir / f"{article.slug}{ext}" for ext in (".md", ".txt")
        ]
        return next((c for c in candidates if c.exists()), None)

    def import_body(self, article, item) -> str:
        source = self.find_text(article, item)
        if source is None:
            return "text: none" if not article.blocks.exists() else "text: kept"
        if article.blocks.exists() and not self.replace_texts:
            return "text: kept (use --replace-texts)"
        article.blocks.all().delete()
        blocks = parse_text(source.read_text(encoding="utf-8"))
        for order, block in enumerate(blocks):
            ArticleBlock.objects.create(article=article, order=order, **block)
        return f"text: {source.name}, {len(blocks)} blocks"


def parse_text(raw: str) -> list[dict]:
    """Plain text -> block dicts. Consecutive paragraphs are merged into one text block."""
    blocks, paragraphs = [], []

    def flush():
        if paragraphs:
            html = "".join(f"<p>{p}</p>" for p in paragraphs)
            blocks.append({"type": ArticleBlock.Type.TEXT, "text": html})
            paragraphs.clear()

    for chunk in re.split(r"\n\s*\n", raw.replace("\r\n", "\n")):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.startswith("## "):
            flush()
            blocks.append({"type": ArticleBlock.Type.HEADING, "heading": chunk[3:].strip()})
        elif chunk.startswith("> "):
            flush()
            lines = [line.removeprefix("> ").removeprefix(">") for line in chunk.splitlines()]
            blocks.append({"type": ArticleBlock.Type.QUOTE, "text": f"<p>{'<br>'.join(escape(l) for l in lines)}</p>"})
        elif chunk in ("***", "---"):
            flush()
            blocks.append({"type": ArticleBlock.Type.DIVIDER})
        else:
            paragraphs.append("<br>".join(escape(line) for line in chunk.splitlines()))
    flush()
    return blocks

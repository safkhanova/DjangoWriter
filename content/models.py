import math
import re
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags

from core.utils import (
    OptimizedImagesMixin,
    is_preview_user,
    sanitize_html,
    unique_slug,
    validate_document_size,
    validate_image_size,
)

# Slugs that would collide with fixed site URLs (/elaqe/, /abune/, ...).
RESERVED_SLUGS = {"elaqe", "abune", "admin", "static", "media", "sitemap.xml", "robots.txt"}

SAFE_LINK_PREFIXES = ("http://", "https://", "mailto:", "tel:", "/", "#")


def is_safe_link(url: str) -> bool:
    """Allowed schemes or a site-relative path; "//host" (protocol-relative) is external, so no."""
    return bool(url) and url.startswith(SAFE_LINK_PREFIXES) and not url.startswith("//")

pdf_validators = [FileExtensionValidator(["pdf"]), validate_document_size]
audio_validators = [FileExtensionValidator(["mp3", "m4a", "ogg", "wav"]), validate_document_size]


def youtube_id(url: str) -> str | None:
    """Extract the video id from any common YouTube URL form."""
    if not url:
        return None
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").removeprefix("www.").removeprefix("m.")
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host in ("youtube.com", "youtube-nocookie.com", "music.youtube.com"):
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        else:
            match = re.match(r"^/(embed|shorts|live|v)/([^/?#]+)", parsed.path)
            candidate = match.group(2) if match else ""
    else:
        return None
    return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate or "") else None


def validate_youtube_url(value):
    if value and not youtube_id(value):
        raise ValidationError("Bu YouTube linki tanınmadı. Videonun linkini brauzerdən və ya «Paylaş» düyməsindən kopyalayın.")


class Section(models.Model):
    class Layout(models.TextChoices):
        FEATURED_LIST = "featured_list", "Seçilmiş yazı + siyahı"
        CARD_GRID = "card_grid", "Kartlar şəbəkəsi"
        TABLE_ARCHIVE = "table_archive", "Cədvəl / arxiv, filtrli"
        DARK_MEDIA = "dark_media", "Video və kartlar, tünd fon"

    class Theme(models.TextChoices):
        LIGHT = "light", "Ağ fon"
        GRAY = "gray", "Açıq boz fon"
        DARK = "dark", "Tünd fon"

    title = models.CharField("Bölmənin adı", max_length=80)
    slug = models.SlugField(
        "Ünvan (URL)", max_length=80, unique=True, blank=True,
        help_text="Boş buraxın — addan avtomatik yaradılır. Məsələn: sayt.az/edebiyyat/",
    )
    number_label = models.CharField(
        "Kartdakı nömrə", max_length=6, blank=True,
        help_text="Məsələn «01». Boş qalsa, sıraya görə avtomatik qoyulur.",
    )
    card_subtitle = models.CharField(
        "Kartdakı qısa təsvir", max_length=120, blank=True, help_text="Məsələn: «Hekayələr və səsli oxu».",
    )
    intro_text = models.TextField("Bölmənin giriş mətni", blank=True)
    layout = models.CharField(
        "Görünüş", max_length=20, choices=Layout.choices, default=Layout.CARD_GRID,
        help_text="Bölmənin ana səhifədə necə görünəcəyi.",
    )
    theme = models.CharField("Fon", max_length=10, choices=Theme.choices, default=Theme.LIGHT)
    order = models.PositiveIntegerField("Sıra", default=0, db_index=True)
    is_visible = models.BooleanField(
        "Saytda görünür", default=True,
        help_text="Söndürsəniz, bölmə və onun bütün yazıları ziyarətçilərdən gizlənir (siz önizləmədə görürsünüz).",
    )
    show_in_nav = models.BooleanField("Yuxarı menyuda göstər", default=True)
    show_in_hero_cards = models.BooleanField("Hero altındakı kartlarda göstər", default=True)
    highlight_card = models.BooleanField("Kartı tünd rənglə vurğula", default=False)
    items_on_homepage = models.PositiveSmallIntegerField(
        "Ana səhifədə neçə yazı göstərilsin", default=4,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    see_all_label = models.CharField("«Hamısı» linkinin mətni", max_length=40, blank=True, default="Hamısı →")
    show_category_filter = models.BooleanField(
        "Növ filtrini göstər", default=False, help_text="«Hamısı / Qəzet / Televiziya» kimi düymələr.",
    )
    cta_label = models.CharField(
        "Əlavə düymənin mətni", max_length=40, blank=True, help_text="Məsələn: «Seansı təyin et». Boş qalsa, düymə yoxdur.",
    )
    cta_topic = models.ForeignKey(
        "core.ContactTopic", verbose_name="Düymə əlaqə formunu bu mövzu ilə açsın",
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    cta_url = models.CharField(
        "və ya düymənin linki", max_length=255, blank=True,
        help_text="Mövzu seçmək əvəzinə xarici link (məs. https://...). Mövzu seçilibsə, boş buraxın.",
    )
    seo_title = models.CharField("SEO başlıq", max_length=70, blank=True)
    seo_description = models.CharField("SEO təsvir", max_length=160, blank=True)

    class Meta:
        verbose_name = "Bölmə"
        verbose_name_plural = "Bölmələr"
        ordering = ["order", "pk"]

    def __str__(self):
        return self.title

    def clean(self):
        if self.slug and self.slug in RESERVED_SLUGS:
            raise ValidationError({"slug": "Bu ünvan sistem tərəfindən istifadə olunur, başqasını seçin."})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title)
            if self.slug in RESERVED_SLUGS:
                self.slug = unique_slug(self, f"{self.title}-bolme")
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("content:section", args=[self.slug])

    @property
    def cta_href(self) -> str:
        if is_safe_link(self.cta_url):
            return self.cta_url
        if self.cta_topic_id:
            return f"{reverse('core:home')}?movzu={self.cta_topic_id}#elaqe"
        return f"{reverse('core:home')}#elaqe"

    def articles_for(self, user):
        return Article.objects.visible_for(user).filter(section=self)


class Category(models.Model):
    """«Növ»: a sub-type inside a section, e.g. Hekayə / Şeir, Qəzet / Televiziya."""

    section = models.ForeignKey(Section, verbose_name="Bölmə", on_delete=models.CASCADE, related_name="categories")
    name = models.CharField("Ad", max_length=60)
    slug = models.SlugField("Ünvan", max_length=80, blank=True)
    order = models.PositiveIntegerField("Sıra", default=0, db_index=True)

    class Meta:
        verbose_name = "Növ"
        verbose_name_plural = "Növlər"
        ordering = ["section__order", "order", "pk"]
        constraints = [models.UniqueConstraint(fields=["section", "slug"], name="unique_category_slug_per_section")]

    def __str__(self):
        return f"{self.section.title} → {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, section=self.section)
        super().save(*args, **kwargs)


class Tag(models.Model):
    name = models.CharField("Ad", max_length=60, unique=True)
    slug = models.SlugField("Ünvan", max_length=80, unique=True, blank=True)

    class Meta:
        verbose_name = "Etiket"
        verbose_name_plural = "Etiketlər"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)


class ArticleQuerySet(models.QuerySet):
    def public(self):
        """What anonymous visitors may see."""
        return self.filter(
            status=Article.Status.PUBLISHED,
            publish_at__lte=timezone.now(),
            section__is_visible=True,
        )

    def visible_for(self, user):
        return self if is_preview_user(user) else self.public()

    def homepage_order(self):
        return self.order_by("-is_featured", "-is_pinned", "-publish_at", "-pk")

    def listing_order(self):
        return self.order_by("-is_pinned", "-publish_at", "-pk")


class Article(OptimizedImagesMixin, models.Model):
    optimized_image_fields = ("cover_image",)

    class Status(models.TextChoices):
        DRAFT = "draft", "Qaralama (yalnız siz görürsünüz)"
        PUBLISHED = "published", "Dərc olunub"

    class Authorship(models.TextChoices):
        OWN = "own", "Mənim yazım"
        INTERVIEW = "interview", "Müsahibə / çıxış (mənim sözlərim)"
        ABOUT = "about", "Haqqımda yazılıb"
        MENTION = "mention", "Adım çəkilib (siyahıda, qısa qeyd)"

    class LinkMode(models.TextChoices):
        PAGE = "page", "Saytda ayrıca səhifə açılsın"
        EXTERNAL = "external", "Xarici link açılsın (qəzet saytı, YouTube ...)"
        PDF = "pdf", "PDF fayl açılsın (skan)"

    section = models.ForeignKey(Section, verbose_name="Bölmə", on_delete=models.PROTECT, related_name="articles")
    category = models.ForeignKey(
        Category, verbose_name="Növ", on_delete=models.SET_NULL, null=True, blank=True, related_name="articles",
        help_text="Seçilmiş bölməyə aid növ (məs. Hekayə, Qəzet).",
    )
    tags = models.ManyToManyField(Tag, verbose_name="Etiketlər", blank=True, related_name="articles")
    authorship = models.CharField(
        "Kim yazıb", max_length=10, choices=Authorship.choices, default=Authorship.OWN, db_index=True,
        help_text="Öz yazınız, müsahibəniz, sizin haqqınızda yazı, yoxsa adınızın sadəcə çəkildiyi yazı "
                  "(məs. müsabiqə qaliblərinin siyahısı).",
    )

    title = models.CharField("Başlıq", max_length=200)
    slug = models.SlugField(
        "Ünvan (URL)", max_length=120, blank=True,
        help_text="Boş buraxın — başlıqdan avtomatik yaradılır.",
    )
    excerpt = models.TextField(
        "Qısa xülasə", blank=True, max_length=400,
        help_text="Kartlarda və siyahılarda görünən 1–2 cümlə.",
    )
    cover_image = models.ImageField("Üz şəkli", upload_to="articles/covers/%Y/", blank=True, validators=[validate_image_size])
    cover_alt = models.CharField("Üz şəklinin təsviri", max_length=160, blank=True)
    show_cover = models.BooleanField("Üz şəklini yazının içində göstər", default=True)

    status = models.CharField("Status", max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    publish_at = models.DateTimeField(
        "Dərc tarixi", default=timezone.now, db_index=True,
        help_text="Gələcək tarix seçsəniz, yazı həmin vaxt avtomatik görünəcək.",
    )
    is_featured = models.BooleanField(
        "Ana səhifədə önə çıxar", default=False,
        help_text="Ana səhifədə bölmənin ilk (böyük) yazısı kimi göstərilir.",
    )
    is_pinned = models.BooleanField(
        "Bölmədə yuxarıda sabitlə", default=False,
        help_text="Bölmə səhifəsində və ana səhifədə digər yazılardan əvvəl göstərilir.",
    )

    link_mode = models.CharField(
        "Kliklənəndə nə açılsın", max_length=10, choices=LinkMode.choices, default=LinkMode.PAGE,
    )
    external_url = models.URLField("Xarici link", blank=True)
    pdf_file = models.FileField("PDF fayl", upload_to="articles/pdf/%Y/", blank=True, validators=pdf_validators)
    source_name = models.CharField(
        "Media / mənbə adı", max_length=120, blank=True, help_text="Qəzetin, jurnalın və ya kanalın adı.",
    )
    source_year = models.PositiveSmallIntegerField(
        "İl", null=True, blank=True, validators=[MinValueValidator(1950), MaxValueValidator(2100)],
    )
    original_author = models.CharField(
        "Yazının müəllifi", max_length=120, blank=True,
        help_text="Müsahibəni və ya yazını hazırlayan jurnalist (məs. «Fatimə Mövlamlı»). Öz yazınız üçün boş qalır.",
    )

    audio_file = models.FileField(
        "Səsli oxu (audio)", upload_to="articles/audio/%Y/", blank=True, validators=audio_validators,
        help_text="Yüklənsə, «Dinlə» düyməsi görünür. MP3 tövsiyə olunur.",
    )
    video_url = models.URLField(
        "Əsas video (YouTube)", blank=True, validators=[validate_youtube_url],
        help_text="«Video və kartlar» görünüşlü bölmələrdə kart video kimi göstərilir.",
    )
    video_duration = models.CharField("Videonun müddəti", max_length=12, blank=True, help_text="Məsələn: 12:40")

    seo_title = models.CharField("SEO başlıq", max_length=70, blank=True)
    seo_description = models.CharField("SEO təsvir", max_length=160, blank=True)

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Müəllif", on_delete=models.SET_NULL, null=True, blank=True, editable=False,
    )
    created_at = models.DateTimeField("Yaradılıb", auto_now_add=True)
    updated_at = models.DateTimeField("Yenilənib", auto_now=True)

    objects = ArticleQuerySet.as_manager()

    class Meta:
        verbose_name = "Yazı"
        verbose_name_plural = "Yazılar"
        ordering = ["-publish_at", "-pk"]
        constraints = [models.UniqueConstraint(fields=["section", "slug"], name="unique_article_slug_per_section")]
        indexes = [models.Index(fields=["section", "status", "publish_at"])]

    def __str__(self):
        return self.title

    def clean(self):
        errors = {}
        if self.category_id and self.section_id and self.category.section_id != self.section_id:
            errors["category"] = f"«{self.category.name}» növü «{self.section}» bölməsinə aid deyil."
        if self.link_mode == self.LinkMode.EXTERNAL and not self.external_url:
            errors["external_url"] = "Xarici link seçilib, amma link yazılmayıb."
        if self.authorship == self.Authorship.OWN and self.original_author:
            errors["original_author"] = "«Mənim yazım» seçilib — başqa müəllif yazmayın, və ya «Haqqımda yazılıb» seçin."
        if self.link_mode == self.LinkMode.PDF and not self.pdf_file:
            errors["pdf_file"] = "PDF seçilib, amma fayl yüklənməyib."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title, max_length=120, section_id=self.section_id)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("content:article", args=[self.section.slug, self.slug])

    @property
    def href(self) -> str:
        """Where a click on the card should go (page, external link or PDF)."""
        if self.link_mode == self.LinkMode.EXTERNAL and self.external_url:
            return self.external_url
        if self.link_mode == self.LinkMode.PDF and self.pdf_file:
            return self.pdf_file.url
        return self.get_absolute_url()

    @property
    def is_own(self) -> bool:
        return self.authorship == self.Authorship.OWN

    @property
    def authorship_label(self) -> str:
        """Short public label; empty for her own writing (the default case needs no badge)."""
        return {
            self.Authorship.INTERVIEW: "Müsahibə",
            self.Authorship.ABOUT: "Haqqımda",
            self.Authorship.MENTION: "Adım çəkilir",
        }.get(self.authorship, "")

    @property
    def opens_new_tab(self) -> bool:
        return self.link_mode != self.LinkMode.PAGE

    @property
    def is_public(self) -> bool:
        return (
            self.status == self.Status.PUBLISHED
            and self.publish_at <= timezone.now()
            and self.section.is_visible
        )

    @property
    def is_scheduled(self) -> bool:
        return self.status == self.Status.PUBLISHED and self.publish_at > timezone.now()

    @property
    def youtube_id(self):
        return youtube_id(self.video_url)

    @property
    def reading_minutes(self) -> int:
        words = sum(len(strip_tags(b.text or "").split()) for b in self.blocks.all() if b.is_visible)
        return max(1, math.ceil(words / 200)) if words else 0


class ArticleBlock(OptimizedImagesMixin, models.Model):
    """One piece of an article's body. Blocks are ordered by drag & drop in the admin."""

    optimized_image_fields = ("image",)

    class Type(models.TextChoices):
        TEXT = "text", "Mətn"
        HEADING = "heading", "Ara başlıq"
        TEXT_IMAGE = "text_image", "Mətn + şəkil yanaşı"
        IMAGE = "image", "Şəkil"
        GALLERY = "gallery", "Qalereya (yazının bütün qalereya şəkilləri)"
        QUOTE = "quote", "Sitat"
        YOUTUBE = "youtube", "YouTube video"
        AUDIO = "audio", "Audio"
        PDF = "pdf", "PDF sənəd"
        BUTTON = "button", "Düymə (link)"
        DIVIDER = "divider", "Ayırıcı xətt"

    class Position(models.TextChoices):
        LEFT = "left", "Solda"
        RIGHT = "right", "Sağda"
        CENTER = "center", "Ortada"
        FULL = "full", "Tam en"

    # Which form fields each block type uses. Drives the admin JS (show/hide)
    # and validation; keep in sync with templates/content/blocks/.
    FIELDS_BY_TYPE = {
        Type.TEXT: ["text"],
        Type.HEADING: ["heading"],
        Type.TEXT_IMAGE: ["heading", "text", "image", "image_alt", "caption", "image_position", "image_width", "text_wrap"],
        Type.IMAGE: ["image", "image_alt", "caption", "image_position", "image_width"],
        Type.GALLERY: ["heading"],
        Type.QUOTE: ["text", "quote_author"],
        Type.YOUTUBE: ["youtube_url", "caption"],
        Type.AUDIO: ["heading", "file", "caption"],
        Type.PDF: ["heading", "file", "button_label"],
        Type.BUTTON: ["button_label", "button_url"],
        Type.DIVIDER: [],
    }

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="blocks")
    type = models.CharField("Blokun növü", max_length=20, choices=Type.choices, default=Type.TEXT)
    order = models.PositiveIntegerField("Sıra", default=0, db_index=True)
    is_visible = models.BooleanField("Görünür", default=True)

    heading = models.CharField("Başlıq", max_length=200, blank=True)
    text = models.TextField("Mətn", blank=True)
    image = models.ImageField("Şəkil", upload_to="articles/blocks/%Y/", blank=True, validators=[validate_image_size])
    image_alt = models.CharField("Şəklin təsviri", max_length=160, blank=True)
    caption = models.CharField("Alt yazı", max_length=255, blank=True)
    image_position = models.CharField(
        "Şəklin yeri", max_length=10, choices=Position.choices, default=Position.RIGHT,
        help_text="«Mətn + şəkil» üçün yalnız Solda / Sağda istifadə olunur.",
    )
    image_width = models.PositiveSmallIntegerField(
        "Şəklin eni (%)", default=40, validators=[MinValueValidator(20), MaxValueValidator(100)],
        help_text="Səhifə eninə görə faiz: 20–100. Telefonda şəkil həmişə tam en olur.",
    )
    text_wrap = models.BooleanField(
        "Mətn şəklin ətrafından axsın", default=True,
        help_text="Söndürsəniz, mətn və şəkil iki ayrı sütun olur.",
    )
    quote_author = models.CharField("Sitatın müəllifi", max_length=120, blank=True)
    youtube_url = models.URLField("YouTube linki", blank=True, validators=[validate_youtube_url])
    file = models.FileField(
        "Fayl", upload_to="articles/files/%Y/", blank=True,
        validators=[FileExtensionValidator(["pdf", "mp3", "m4a", "ogg", "wav"]), validate_document_size],
    )
    button_label = models.CharField("Düymənin mətni", max_length=60, blank=True)
    button_url = models.CharField("Düymənin linki", max_length=500, blank=True)

    class Meta:
        verbose_name = "Məzmun bloku"
        verbose_name_plural = "Məzmun blokları"
        ordering = ["order", "pk"]

    def __str__(self):
        return self.get_type_display()

    def clean(self):
        t, errors = self.Type, {}
        if self.type in (t.TEXT, t.TEXT_IMAGE, t.QUOTE) and not strip_tags(self.text or "").strip():
            errors["text"] = "Mətn yazın."
        if self.type == t.HEADING and not self.heading:
            errors["heading"] = "Başlığı yazın."
        if self.type in (t.IMAGE, t.TEXT_IMAGE) and not self.image:
            errors["image"] = "Şəkil yükləyin."
        if self.type == t.TEXT_IMAGE and self.image_position not in (self.Position.LEFT, self.Position.RIGHT):
            errors["image_position"] = "«Mətn + şəkil» üçün «Solda» və ya «Sağda» seçin."
        if self.type == t.TEXT_IMAGE and self.image_width > 70:
            errors["image_width"] = "Mətnin yanında şəkil ən çox 70% ola bilər."
        if self.type == t.YOUTUBE and not self.youtube_url:
            errors["youtube_url"] = "YouTube linkini yazın."
        if self.type == t.AUDIO and self.file and not self.file.name.lower().endswith((".mp3", ".m4a", ".ogg", ".wav")):
            errors["file"] = "Audio fayl yükləyin (MP3)."
        if self.type == t.PDF and self.file and not self.file.name.lower().endswith(".pdf"):
            errors["file"] = "PDF fayl yükləyin."
        if self.type in (t.AUDIO, t.PDF) and not self.file:
            errors["file"] = "Fayl yükləyin."
        if self.type == t.BUTTON and not (self.button_label and self.button_url):
            errors["button_label"] = "Düymənin mətnini və linkini yazın."
        if self.button_url and not is_safe_link(self.button_url):
            errors["button_url"] = "Link https://, mailto:, tel:, / və ya # ilə başlamalıdır."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.text = sanitize_html(self.text)
        super().save(*args, **kwargs)

    @property
    def youtube_id(self):
        return youtube_id(self.youtube_url)

    @property
    def template_name(self) -> str:
        return f"content/blocks/{self.type}.html"


class ArticleImage(OptimizedImagesMixin, models.Model):
    """Gallery images of an article, shown by a «Qalereya» block."""

    optimized_image_fields = ("image",)

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="gallery")
    image = models.ImageField("Şəkil", upload_to="articles/gallery/%Y/", validators=[validate_image_size])
    alt = models.CharField("Təsvir", max_length=160, blank=True)
    caption = models.CharField("Alt yazı", max_length=255, blank=True)
    order = models.PositiveIntegerField("Sıra", default=0, db_index=True)

    class Meta:
        verbose_name = "Qalereya şəkli"
        verbose_name_plural = "Qalereya şəkilləri"
        ordering = ["order", "pk"]

    def __str__(self):
        return self.alt or f"Şəkil #{self.pk}"


def visible_sections(user):
    qs = Section.objects.all()
    return qs if is_preview_user(user) else qs.filter(is_visible=True)


__all__ = [
    "Section", "Category", "Tag", "Article", "ArticleBlock", "ArticleImage",
    "youtube_id", "visible_sections",
]

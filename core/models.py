from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from .design import COLOR_CHOICES, COLOR_PRESETS, FONT_CHOICES, FONT_PRESETS
from .utils import OptimizedImagesMixin, favicon_validators, logo_validators, validate_image_size


class SiteSettings(OptimizedImagesMixin, models.Model):
    """Global settings. Singleton: always exactly one row (pk=1)."""

    optimized_image_fields = ("og_image",)

    site_name = models.CharField("Saytın adı (loqo mətni)", max_length=80, default="Adınız Soyadınız")
    logo = models.FileField(
        "Loqo (istəyə görə)", upload_to="site/", blank=True, validators=logo_validators,
        help_text="Boş qalsa, yuxarıda saytın adı mətn kimi göstərilir. SVG və ya PNG.",
    )
    favicon = models.FileField(
        "Brauzer ikonu (favicon)", upload_to="site/", blank=True, validators=favicon_validators,
        help_text="ICO, PNG və ya SVG.",
    )
    font_preset = models.CharField(
        "Şrift dəsti", max_length=40, choices=FONT_CHOICES, default="inter_fraunces",
        help_text="Bütün sayt üçün başlıq və mətn şriftləri. Hero öz şriftini ayrıca seçə bilər.",
    )
    color_preset = models.CharField("Əsas rəng", max_length=40, choices=COLOR_CHOICES, default="green")
    nav_cta_label = models.CharField("Menyudakı düymənin mətni", max_length=40, default="Əlaqə", blank=True)
    contact_title = models.CharField("Əlaqə bölməsinin başlığı", max_length=80, default="Əlaqə")
    contact_text = models.TextField(
        "Əlaqə bölməsinin mətni", blank=True,
        default="Əməkdaşlıq və suallar üçün yazın.",
    )
    contact_email = models.EmailField(
        "Saytda göstərilən e-poçt", blank=True,
    )
    notification_email = models.EmailField(
        "Mesajların gələcəyi e-poçt", blank=True,
        help_text="Əlaqə formundan gələn mesajlar bu ünvana göndərilir.",
    )
    show_contact_section = models.BooleanField("Əlaqə bölməsini göstər", default=True)
    show_subscribe_box = models.BooleanField(
        "Abunə formunu göstər", default=True,
        help_text="Ziyarətçilər yeni yazılar haqqında e-poçt almaq üçün abunə ola bilər.",
    )
    subscribe_title = models.CharField("Abunə formunun başlığı", max_length=120, default="Yeni yazılardan xəbərdar olun")
    subscribe_text = models.CharField(
        "Abunə formunun mətni", max_length=255, blank=True,
        default="Maraqlandığınız bölmələri seçin, yeni yazı çıxanda e-poçtla xəbər verək.",
    )
    footer_text = models.CharField("Altlıq mətni", max_length=255, blank=True, default="")
    seo_title = models.CharField("Axtarış sistemləri üçün başlıq", max_length=70, blank=True)
    seo_description = models.CharField("Axtarış sistemləri üçün təsvir", max_length=160, blank=True)
    og_image = models.ImageField(
        "Paylaşım şəkli", upload_to="site/", blank=True, validators=[validate_image_size],
        help_text="Link WhatsApp, Facebook və s.-də paylaşılanda görünən şəkil (1200×630 tövsiyə olunur).",
    )
    analytics_snippet = models.TextField(
        "Statistika kodu (yalnız administrator)", blank=True,
        help_text="Plausible/Umami skript teqi (<script src=...>). Səhifənin <head> hissəsinə əlavə olunur. "
                  "Domeni .env faylında CSP_EXTRA_SCRIPT_SRC-ə də əlavə edin, yoxsa brauzer bloklayacaq.",
    )

    class Meta:
        verbose_name = "Sayt ayarları"
        verbose_name_plural = "Sayt ayarları"

    def __str__(self):
        return "Sayt ayarları"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # singleton cannot be deleted

    @classmethod
    def load(cls) -> "SiteSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def fonts(self) -> dict:
        return FONT_PRESETS.get(self.font_preset, FONT_PRESETS["inter_fraunces"])

    @property
    def colors(self) -> dict:
        return COLOR_PRESETS.get(self.color_preset, COLOR_PRESETS["green"])


class Hero(OptimizedImagesMixin, models.Model):
    """
    The intro block at the top of the home page.

    Several versions can be prepared (e.g. "Yay 2026", "Kitab təqdimatı");
    only one is active at a time, the others act as drafts.
    """

    optimized_image_fields = ("portrait",)

    class PortraitPosition(models.TextChoices):
        RIGHT = "right", "Sağda"
        LEFT = "left", "Solda"
        NONE = "none", "Şəkilsiz"

    name = models.CharField(
        "Versiyanın adı (yalnız sizə görünür)", max_length=80,
        help_text="Məsələn: «Əsas», «Yeni kitab təqdimatı».",
    )
    is_active = models.BooleanField(
        "Aktiv", default=False,
        help_text="Saytda yalnız bir aktiv versiya göstərilir. Bunu aktiv etsəniz, digəri avtomatik qaralamaya keçir.",
    )
    title_line_1 = models.CharField("Başlıq — 1-ci sətir", max_length=120)
    title_line_2 = models.CharField(
        "Başlıq — 2-ci sətir (kursiv, rəngli)", max_length=160, blank=True,
    )
    intro_text = models.TextField("Qısa təqdimat", blank=True)
    portrait = models.ImageField(
        "Portret şəkli", upload_to="hero/", blank=True, validators=[validate_image_size],
    )
    portrait_alt = models.CharField(
        "Şəklin təsviri", max_length=160, blank=True,
        help_text="Görmə məhdudiyyətli oxucular və Google üçün. Məsələn: «Müəllifin portreti».",
    )
    portrait_position = models.CharField(
        "Şəklin yeri", max_length=10, choices=PortraitPosition.choices, default=PortraitPosition.RIGHT,
    )
    font_preset = models.CharField(
        "Başlıq şrifti", max_length=40, choices=FONT_CHOICES, blank=True,
        help_text="Boş qalsa, sayt ayarlarındakı şrift istifadə olunur.",
    )
    show_section_cards = models.BooleanField(
        "Bölmə kartlarını göstər", default=True,
        help_text="Hero altında bölmələrin nömrəli kartları (01, 02 ...).",
    )
    updated_at = models.DateTimeField("Yenilənib", auto_now=True)

    class Meta:
        verbose_name = "Hero versiyası"
        verbose_name_plural = "Hero (giriş bloku)"
        ordering = ["-is_active", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"], condition=models.Q(is_active=True), name="only_one_active_hero",
            )
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_active:
                Hero.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
            super().save(*args, **kwargs)

    def activate(self):
        self.is_active = True
        self.save()

    @property
    def fonts(self) -> dict | None:
        return FONT_PRESETS.get(self.font_preset) if self.font_preset else None


class HeroTag(models.Model):
    hero = models.ForeignKey(Hero, on_delete=models.CASCADE, related_name="tags")
    label = models.CharField("Etiket", max_length=40)
    is_visible = models.BooleanField("Görünür", default=True)
    order = models.PositiveIntegerField("Sıra", default=0, db_index=True)

    class Meta:
        verbose_name = "Etiket"
        verbose_name_plural = "Etiketlər (başlığın üstündəki kiçik nişanlar)"
        ordering = ["order", "pk"]

    def __str__(self):
        return self.label


class SocialLink(models.Model):
    class Icon(models.TextChoices):
        INSTAGRAM = "instagram", "Instagram"
        FACEBOOK = "facebook", "Facebook"
        LINKEDIN = "linkedin", "LinkedIn"
        YOUTUBE = "youtube", "YouTube"
        TELEGRAM = "telegram", "Telegram"
        X = "x", "X (Twitter)"
        TIKTOK = "tiktok", "TikTok"
        WEBSITE = "website", "Digər sayt"

    name = models.CharField("Ad", max_length=40, help_text="Saytda göstərilən mətn.")
    icon = models.CharField("Növ", max_length=20, choices=Icon.choices, default=Icon.WEBSITE)
    url = models.URLField("Link")
    is_visible = models.BooleanField("Görünür", default=True)
    order = models.PositiveIntegerField("Sıra", default=0, db_index=True)

    class Meta:
        verbose_name = "Sosial şəbəkə"
        verbose_name_plural = "Sosial şəbəkələr"
        ordering = ["order", "pk"]

    def __str__(self):
        return self.name


class ContactTopic(models.Model):
    name = models.CharField("Mövzu", max_length=80)
    is_visible = models.BooleanField("Formda göstər", default=True)
    order = models.PositiveIntegerField("Sıra", default=0, db_index=True)

    class Meta:
        verbose_name = "Mesaj mövzusu"
        verbose_name_plural = "Mesaj mövzuları"
        ordering = ["order", "pk"]

    def __str__(self):
        return self.name


class ContactMessage(models.Model):
    name = models.CharField("Ad", max_length=120)
    email = models.EmailField("E-poçt")
    phone = models.CharField("Telefon", max_length=40, blank=True)
    topic = models.ForeignKey(
        ContactTopic, verbose_name="Mövzu", on_delete=models.SET_NULL, null=True, blank=True,
    )
    message = models.TextField("Mesaj")
    created_at = models.DateTimeField("Göndərilib", default=timezone.now, db_index=True)
    is_read = models.BooleanField("Oxunub", default=False)
    is_archived = models.BooleanField("Arxivdə", default=False)
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)

    class Meta:
        verbose_name = "Mesaj"
        verbose_name_plural = "Mesajlar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} — {self.topic or 'mövzusuz'}"

    def clean(self):
        if not self.message.strip():
            raise ValidationError({"message": "Mesaj boş ola bilməz."})


class UserSession(models.Model):
    """
    One row per logged-in browser, so sessions can be listed and revoked.

    Revoking deletes the Django session row (database session backend), which
    logs that browser out on its very next request. See core/sessions.py.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="İstifadəçi", on_delete=models.CASCADE, related_name="tracked_sessions",
    )
    session_key = models.CharField("Sessiya açarı", max_length=40, unique=True)
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.CharField("Brauzer", max_length=300, blank=True)
    created_at = models.DateTimeField("Giriş vaxtı", default=timezone.now)
    last_seen_at = models.DateTimeField("Son fəaliyyət", default=timezone.now)

    class Meta:
        verbose_name = "Aktiv sessiya"
        verbose_name_plural = "Aktiv sessiyalar"
        ordering = ["-last_seen_at"]

    def __str__(self):
        return f"{self.user} — {self.device}"

    @property
    def device(self) -> str:
        ua = self.user_agent.lower()
        os_name = next(
            (name for key, name in (("iphone", "iPhone"), ("ipad", "iPad"), ("android", "Android"),
                                    ("mac os", "Mac"), ("windows", "Windows"), ("linux", "Linux")) if key in ua),
            "Naməlum cihaz",
        )
        browser = next(
            (name for key, name in (("edg/", "Edge"), ("firefox", "Firefox"), ("chrome", "Chrome"),
                                    ("safari", "Safari")) if key in ua),
            "",
        )
        return f"{os_name} · {browser}" if browser else os_name

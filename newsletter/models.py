import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


class SubscriberQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_confirmed=True, unsubscribed_at__isnull=True)

    def interested_in(self, section):
        """Subscribers who chose this section, or chose nothing (= everything)."""
        return self.active().filter(Q(sections=section) | Q(sections__isnull=True)).distinct()


class Subscriber(models.Model):
    email = models.EmailField("E-poçt", unique=True)
    name = models.CharField("Ad", max_length=120, blank=True)
    sections = models.ManyToManyField(
        "content.Section", verbose_name="Maraqlandığı bölmələr", blank=True, related_name="subscribers",
        help_text="Heç biri seçilməyibsə, bütün bölmələrin yazılarını alır.",
    )
    token = models.UUIDField("Gizli açar", default=uuid.uuid4, unique=True, editable=False)
    is_confirmed = models.BooleanField(
        "Təsdiqlənib", default=False, help_text="Abunəçi e-poçtdakı linkə klikləyib.",
    )
    created_at = models.DateTimeField("Abunə tarixi", default=timezone.now)
    confirmed_at = models.DateTimeField("Təsdiq tarixi", null=True, blank=True)
    unsubscribed_at = models.DateTimeField("İmtina tarixi", null=True, blank=True)

    objects = SubscriberQuerySet.as_manager()

    class Meta:
        verbose_name = "Abunəçi"
        verbose_name_plural = "Abunəçilər"
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    @property
    def is_active(self) -> bool:
        return self.is_confirmed and self.unsubscribed_at is None

    def confirm_url(self) -> str:
        return settings.SITE_URL + reverse("newsletter:confirm", args=[self.token])

    def manage_url(self) -> str:
        return settings.SITE_URL + reverse("newsletter:manage", args=[self.token])

    def one_click_unsubscribe_url(self) -> str:
        return settings.SITE_URL + reverse("newsletter:one_click_unsubscribe", args=[self.token])


class NewsletterIssue(models.Model):
    """A notification about one article. One per article, so it can never be sent twice by mistake."""

    article = models.OneToOneField(
        "content.Article", verbose_name="Yazı", on_delete=models.CASCADE, related_name="newsletter_issue",
    )
    subject = models.CharField("Mövzu", max_length=200)
    created_at = models.DateTimeField("Yaradılıb", default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Göndərən", on_delete=models.SET_NULL, null=True, blank=True,
    )
    recipients_count = models.PositiveIntegerField("Alıcı sayı", default=0)

    class Meta:
        verbose_name = "Bülleten"
        verbose_name_plural = "Göndərilən bülletenlər"
        ordering = ["-created_at"]

    def __str__(self):
        return self.subject

    @property
    def sent_count(self) -> int:
        return self.emails.filter(status=OutgoingEmail.Status.SENT).count()


class OutgoingEmail(models.Model):
    """E-mail queue, drained by `manage.py send_queued_emails` (cron, every minute)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Növbədə"
        SENT = "sent", "Göndərilib"
        FAILED = "failed", "Xəta"

    MAX_ATTEMPTS = 3

    issue = models.ForeignKey(
        NewsletterIssue, on_delete=models.CASCADE, null=True, blank=True, related_name="emails",
    )
    to_email = models.EmailField("Kimə")
    reply_to = models.EmailField("Cavab ünvanı", blank=True)
    subject = models.CharField("Mövzu", max_length=200)
    body_text = models.TextField("Mətn")
    body_html = models.TextField("HTML", blank=True)
    unsubscribe_url = models.URLField("İmtina linki", blank=True)
    status = models.CharField("Status", max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempts = models.PositiveSmallIntegerField("Cəhd sayı", default=0)
    last_error = models.TextField("Son xəta", blank=True)
    created_at = models.DateTimeField("Yaradılıb", default=timezone.now)
    sent_at = models.DateTimeField("Göndərilib", null=True, blank=True)

    class Meta:
        verbose_name = "E-poçt"
        verbose_name_plural = "E-poçt növbəsi"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.to_email}: {self.subject}"

"""E-mail building and delivery. Everything goes through the OutgoingEmail queue."""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from core.models import SiteSettings

from .models import NewsletterIssue, OutgoingEmail, Subscriber

logger = logging.getLogger(__name__)


def _render(template: str, context: dict) -> tuple[str, str]:
    context = {"site": SiteSettings.load(), "SITE_URL": settings.SITE_URL, **context}
    return (
        render_to_string(f"emails/{template}.txt", context),
        render_to_string(f"emails/{template}.html", context),
    )


def deliver(email: OutgoingEmail) -> bool:
    """Send one queued e-mail now. Never raises; records the outcome on the row."""
    message = EmailMultiAlternatives(
        subject=email.subject,
        body=email.body_text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email.to_email],
        reply_to=[email.reply_to] if email.reply_to else None,
        headers=(
            {
                "List-Unsubscribe": f"<{email.unsubscribe_url}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            }
            if email.unsubscribe_url
            else None
        ),
    )
    if email.body_html:
        message.attach_alternative(email.body_html, "text/html")
    email.attempts += 1
    try:
        message.send()
    except Exception as exc:  # SMTP down, bad address...
        logger.warning("E-mail to %s failed: %s", email.to_email, exc)
        email.last_error = str(exc)[:2000]
        if email.attempts >= OutgoingEmail.MAX_ATTEMPTS:
            email.status = OutgoingEmail.Status.FAILED
        email.save(update_fields=["attempts", "last_error", "status"])
        return False
    email.status = OutgoingEmail.Status.SENT
    email.sent_at = timezone.now()
    email.last_error = ""
    email.save(update_fields=["attempts", "last_error", "status", "sent_at"])
    return True


def send_now(to: str, subject: str, template: str, context: dict, reply_to: str | None = None) -> bool:
    """Transactional e-mail (confirmation, contact notification): queue it and try at once."""
    text, html = _render(template, context)
    email = OutgoingEmail.objects.create(
        to_email=to, subject=subject, body_text=text, body_html=html, reply_to=reply_to or "",
    )
    return deliver(email)


def send_confirmation(subscriber: Subscriber) -> bool:
    site = SiteSettings.load()
    return send_now(
        subscriber.email,
        f"Abunəliyi təsdiqləyin — {site.site_name}",
        "confirm_subscription",
        {"subscriber": subscriber},
    )


@transaction.atomic
def queue_article_newsletter(article, user=None) -> NewsletterIssue:
    """
    Create the newsletter for `article` and queue one e-mail per interested subscriber.

    Raises ValueError if the article is not public or was already sent.
    """
    if not article.is_public:
        raise ValueError("Yazı hələ dərc olunmayıb. Əvvəlcə dərc edin, sonra göndərin.")
    if NewsletterIssue.objects.filter(article=article).exists():
        raise ValueError("Bu yazı artıq abunəçilərə göndərilib.")

    site = SiteSettings.load()
    subject = f"Yeni yazı: {article.title}"
    issue = NewsletterIssue.objects.create(article=article, subject=subject, created_by=user)
    article_url = settings.SITE_ORIGIN + article.get_absolute_url()

    rows = []
    for subscriber in Subscriber.objects.interested_in(article.section):
        text, html = _render(
            "new_article",
            {"article": article, "article_url": article_url, "subscriber": subscriber, "site": site},
        )
        rows.append(
            OutgoingEmail(
                issue=issue,
                to_email=subscriber.email,
                subject=subject,
                body_text=text,
                body_html=html,
                unsubscribe_url=subscriber.one_click_unsubscribe_url(),
            )
        )
    OutgoingEmail.objects.bulk_create(rows)
    issue.recipients_count = len(rows)
    issue.save(update_fields=["recipients_count"])
    return issue


def send_queued(limit: int | None = None) -> tuple[int, int]:
    """Send pending e-mails. Returns (sent, failed)."""
    limit = limit or settings.NEWSLETTER_BATCH_SIZE
    sent = failed = 0
    pending = OutgoingEmail.objects.filter(status=OutgoingEmail.Status.PENDING).order_by("created_at")[:limit]
    for email in pending:
        if deliver(email):
            sent += 1
        else:
            failed += 1
    return sent, failed

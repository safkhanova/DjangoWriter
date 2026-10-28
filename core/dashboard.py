"""Admin home page (Unfold DASHBOARD_CALLBACK) and sidebar badges."""

from django.urls import reverse

from content.models import Article, Section
from newsletter.models import Subscriber

from .models import ContactMessage, Hero


def unread_messages_badge(request):
    count = ContactMessage.objects.filter(is_read=False, is_archived=False).count()
    return count or None


def dashboard_callback(request, context):
    drafts = Article.objects.filter(status=Article.Status.DRAFT).select_related("section").order_by("-updated_at")[:6]
    recent = Article.objects.select_related("section").order_by("-updated_at")[:6]
    context.update(
        {
            "quick_actions": [
                {"title": "Yeni yazı", "icon": "add_circle", "url": reverse("admin:content_article_add")},
                {"title": "Bütün yazılar", "icon": "article", "url": reverse("admin:content_article_changelist")},
                {"title": "Hero (giriş bloku)", "icon": "web_asset", "url": reverse("admin:core_hero_changelist")},
                {"title": "Bölmələr", "icon": "view_agenda", "url": reverse("admin:content_section_changelist")},
                {"title": "Sayt ayarları", "icon": "tune", "url": reverse("admin:core_sitesettings_changelist")},
                {"title": "Saytı aç", "icon": "open_in_new", "url": reverse("core:home"), "new_tab": True},
            ],
            "stats": [
                {"title": "Dərc olunmuş yazılar", "value": Article.objects.public().count()},
                {"title": "Qaralamalar", "value": Article.objects.filter(status=Article.Status.DRAFT).count()},
                {"title": "Yeni mesajlar", "value": ContactMessage.objects.filter(is_read=False, is_archived=False).count(),
                 "url": reverse("admin:core_contactmessage_changelist") + "?is_read__exact=0"},
                {"title": "Aktiv abunəçilər", "value": Subscriber.objects.active().count()},
            ],
            "drafts": drafts,
            "recent": recent,
            "active_hero": Hero.objects.filter(is_active=True).first(),
            "hidden_sections": Section.objects.filter(is_visible=False),
        }
    )
    return context

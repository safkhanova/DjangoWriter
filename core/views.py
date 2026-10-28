import logging

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import get_script_prefix, reverse
from django.views.decorators.http import require_GET, require_POST

from content.models import Article, visible_sections
from core.utils import is_preview_user
from emailotp.services import client_ip
from newsletter.forms import SubscribeForm
from newsletter.services import send_now

from .forms import ContactForm, rate_limited, single_line
from .models import Hero, SiteSettings

logger = logging.getLogger(__name__)


def current_hero(request):
    """Active hero; staff can preview any version with ?hero=<id>."""
    if is_preview_user(request.user) and request.GET.get("hero", "").isdigit():
        hero = Hero.objects.filter(pk=request.GET["hero"]).first()
        if hero:
            return hero
    return Hero.objects.filter(is_active=True).prefetch_related("tags").first()


def home(request):
    sections = list(visible_sections(request.user).prefetch_related("categories"))
    for section in sections:
        section.home_articles = list(
            Article.objects.visible_for(request.user)
            .filter(section=section)
            .select_related("category", "section")
            .homepage_order()[: section.items_on_homepage]
        )

    topic = request.GET.get("movzu", "")
    contact_form = ContactForm(initial={"topic": topic} if topic.isdigit() else None)
    hero = current_hero(request)
    return render(
        request,
        "site/home.html",
        {
            "hero": hero,
            "hero_tags": [t for t in hero.tags.all() if t.is_visible] if hero else [],
            "sections": sections,
            "hero_sections": [s for s in sections if s.show_in_hero_cards],
            "contact_form": contact_form,
            "subscribe_form": SubscribeForm(),
        },
    )


@require_POST
def contact(request):
    form = ContactForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Formda səhv var. Zəhmət olmasa sahələri yoxlayın.")
        return render(request, "site/contact_page.html", {"contact_form": form}, status=400)
    if form.is_spam() or rate_limited(request, "contact"):
        # Pretend success: bots get no signal.
        messages.success(request, "Təşəkkürlər! Mesajınız göndərildi.")
        return redirect(reverse("core:home") + "#elaqe")

    msg = form.save(commit=False)
    msg.ip_address = client_ip(request) or None
    msg.save()

    site = SiteSettings.load()
    if site.notification_email:
        send_now(
            site.notification_email,
            f"Saytdan yeni mesaj: {msg.topic or 'mövzusuz'} — {single_line(msg.name)}",
            "contact_notification",
            {"msg": msg},
            reply_to=msg.email,
        )
    messages.success(request, "Təşəkkürlər! Mesajınız göndərildi. Tezliklə cavab verəcəyəm.")
    return redirect(reverse("core:home") + "#elaqe")


@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        f"Disallow: {get_script_prefix()}login/",
        f"Disallow: {get_script_prefix()}abune/",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


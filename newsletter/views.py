from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.forms import rate_limited

from .forms import PreferencesForm, SubscribeForm
from .models import Subscriber
from .services import send_confirmation

GENERIC_OK = "Təsdiq linki e-poçtunuza göndərildi. Abunəliyi tamamlamaq üçün linkə klikləyin."


@require_POST
def subscribe(request):
    form = SubscribeForm(request.POST)
    if not form.is_valid():
        return render(request, "newsletter/subscribe_page.html", {"form": form}, status=400)
    if form.is_spam() or rate_limited(request, "subscribe"):
        messages.success(request, GENERIC_OK)
        return redirect(reverse("core:home") + "#abune")

    email = form.cleaned_data["email"]
    subscriber, created = Subscriber.objects.get_or_create(
        email=email, defaults={"name": form.cleaned_data["name"]},
    )
    if subscriber.is_active:
        # Already subscribed: same message on screen (do not reveal who is subscribed),
        # preferences can be changed via the link in any received e-mail.
        messages.success(request, GENERIC_OK)
        return redirect(reverse("core:home") + "#abune")

    # New, unconfirmed or previously unsubscribed: (re)start double opt-in.
    subscriber.sections.set(form.cleaned_data["sections"])
    if form.cleaned_data["name"]:
        subscriber.name = form.cleaned_data["name"]
    subscriber.unsubscribed_at = None
    subscriber.is_confirmed = False
    subscriber.save()
    send_confirmation(subscriber)
    messages.success(request, GENERIC_OK)
    return redirect(reverse("core:home") + "#abune")


def confirm(request, token):
    subscriber = get_object_or_404(Subscriber, token=token)
    if not subscriber.is_confirmed or subscriber.unsubscribed_at:
        subscriber.is_confirmed = True
        subscriber.confirmed_at = timezone.now()
        subscriber.unsubscribed_at = None
        subscriber.save(update_fields=["is_confirmed", "confirmed_at", "unsubscribed_at"])
    return render(request, "newsletter/confirmed.html", {"subscriber": subscriber})


def manage(request, token):
    """Change sections or unsubscribe. Reached from the link in every e-mail."""
    subscriber = get_object_or_404(Subscriber, token=token)
    if request.method == "POST" and "unsubscribe" in request.POST:
        subscriber.unsubscribed_at = timezone.now()
        subscriber.save(update_fields=["unsubscribed_at"])
        return render(request, "newsletter/unsubscribed.html", {"subscriber": subscriber})

    form = PreferencesForm(request.POST or None, initial={"sections": subscriber.sections.all()})
    if request.method == "POST" and form.is_valid():
        subscriber.sections.set(form.cleaned_data["sections"])
        if subscriber.unsubscribed_at:
            subscriber.unsubscribed_at = None
            subscriber.save(update_fields=["unsubscribed_at"])
        messages.success(request, "Seçimləriniz yadda saxlanıldı.")
        return redirect("newsletter:manage", token=token)
    return render(request, "newsletter/manage.html", {"subscriber": subscriber, "form": form})


@csrf_exempt
@require_POST
def one_click_unsubscribe(request, token):
    """RFC 8058 List-Unsubscribe-Post target (Gmail / Apple Mail button)."""
    Subscriber.objects.filter(token=token).update(unsubscribed_at=timezone.now())
    return render(request, "newsletter/unsubscribed.html", {})

"""
Session tracking and revocation ("log out everywhere").

Requires the database session backend (SESSION_ENGINE = "django.contrib.sessions.backends.db"):
revoking = deleting the `django_session` row, so the stolen cookie points at nothing and the
next request is anonymous. Changing a user's password also invalidates all their sessions
(Django's session auth hash); deactivating the user blocks them entirely.
"""

from datetime import timedelta

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.sessions.models import Session
from django.dispatch import receiver
from django.utils import timezone

from emailotp.services import client_ip

from .models import UserSession

TOUCH_INTERVAL = timedelta(minutes=5)


def track(request, user) -> None:
    key = request.session.session_key
    if not key:
        request.session.save()
        key = request.session.session_key
    UserSession.objects.update_or_create(
        session_key=key,
        defaults={
            "user": user,
            "ip_address": client_ip(request) or None,
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300],
            "last_seen_at": timezone.now(),
        },
    )


def revoke_sessions(sessions) -> int:
    """Delete the given UserSession rows and their Django sessions. Returns how many."""
    keys = list(sessions.values_list("session_key", flat=True))
    Session.objects.filter(session_key__in=keys).delete()
    sessions.model.objects.filter(session_key__in=keys).delete()
    return len(keys)


def revoke_user_sessions(user, except_key: str | None = None) -> int:
    qs = UserSession.objects.filter(user=user)
    if except_key:
        qs = qs.exclude(session_key=except_key)
    count = revoke_sessions(qs)
    # Sessions created before tracking existed (or not tracked for any reason) are found by
    # decoding: slower, but this runs only on an explicit revoke.
    for session in Session.objects.filter(expire_date__gt=timezone.now()):
        if session.session_key != except_key and str(session.get_decoded().get("_auth_user_id")) == str(user.pk):
            session.delete()
            count += 1
    return count


def purge_stale() -> int:
    """Remove tracking rows whose Django session expired or no longer exists."""
    live = Session.objects.filter(expire_date__gt=timezone.now()).values("session_key")
    deleted, _ = UserSession.objects.exclude(session_key__in=live).delete()
    return deleted


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    if request is not None and hasattr(request, "session"):
        track(request, user)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if request is not None and request.session.session_key:
        UserSession.objects.filter(session_key=request.session.session_key).delete()


class SessionActivityMiddleware:
    """Keeps `last_seen_at` fresh (at most every 5 minutes) and tracks untracked logged-in sessions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and request.session.session_key:
            key = request.session.session_key
            now = timezone.now()
            updated = UserSession.objects.filter(
                session_key=key, last_seen_at__lt=now - TOUCH_INTERVAL,
            ).update(last_seen_at=now)
            if not updated and not UserSession.objects.filter(session_key=key).exists():
                track(request, user)
        return self.get_response(request)

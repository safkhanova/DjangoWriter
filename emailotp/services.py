"""
emailotp/services.py — everything the views need that isn't a view.
"""
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from . import conf
from .models import AuthEvent, EmailOTP
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

def get_user_by_email(email, active_only=True):
    """Look up a user by the configured field (username by default)."""
    lookup = {conf.LOOKUP_FIELD: email}
    if active_only:
        lookup['is_active'] = True
    return User.objects.filter(**lookup).first()


def client_ip(request):
    """
    Trust X-Real-IP only.

    nginx's `proxy_set_header X-Real-IP $remote_addr` overwrites whatever the
    client sent, so the value is trustworthy. X-Forwarded-For is deliberately
    NOT used: `$proxy_add_x_forwarded_for` appends to the client's own header,
    so its leftmost value is attacker-controlled and an IP limit keyed on it
    can be bypassed by sending a different fake value each request.

    If your proxy sets a different header, override this via
    EMAILOTP_IP_HEADER.
    """
    header = getattr(settings, 'EMAILOTP_IP_HEADER', 'HTTP_X_REAL_IP')
    return request.META.get(header) or request.META.get('REMOTE_ADDR')


def log(kind, request, email='', ip=None):
    """Write one audit row. Never raises into the request path."""
    try:
        AuthEvent.objects.create(
            kind=kind,
            email=email or '',
            ip=ip if ip is not None else client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
        )
    except Exception:  # pragma: no cover - audit must never break login
        pass


def sending_allowed(email, ip):
    """
    All three send-side rate limits.

    Returns True/False and never explains which limit fired — the caller shows
    the same screen either way, so a prober learns nothing.
    """
    now = timezone.now()
    qs = EmailOTP.objects
    if qs.filter(email=email, created_at__gte=now - conf.RESEND_COOLDOWN).exists():
        return False
    if qs.filter(
        email=email, created_at__gte=now - timedelta(hours=24)
    ).count() >= conf.MAX_PER_EMAIL_24H:
        return False
    if ip and qs.filter(
        request_ip=ip, created_at__gte=now - timedelta(hours=1)
    ).count() >= conf.MAX_PER_IP_1H:
        return False
    return True


def verify_allowed(ip):
    """
    Verify-side per-IP limit.

    EmailOTP.attempts caps guesses against one code, but a fresh code resets
    it, and each email address gets its own budget. This is what stops one
    host from spreading guesses across thousands of addresses.

    Kept deliberately generous: mobile and office networks put many people
    behind one address, and the per-code counter does the real anti-guessing
    work.
    """
    if not ip:
        return True
    since = timezone.now() - timedelta(hours=1)
    return AuthEvent.objects.filter(
        kind=AuthEvent.VERIFY_FAIL, ip=ip, created_at__gte=since
    ).count() < conf.MAX_VERIFY_FAIL_PER_IP_1H


def issue_otp(email, ip):
    """Invalidate previous codes, create a new one, email it."""
    from django.contrib.auth.hashers import make_password

    EmailOTP.objects.filter(email=email, used=False).update(used=True)

    upper = 10 ** conf.CODE_DIGITS
    code = str(secrets.randbelow(upper)).zfill(conf.CODE_DIGITS)

    otp = EmailOTP.objects.create(
        email=email,
        code_hash=make_password(code),
        expires_at=timezone.now() + conf.OTP_LIFETIME,
        request_ip=ip,
    )

    context = {
        'code': code,
        'site_name': conf.SITE_NAME,
        'minutes': int(conf.OTP_LIFETIME.total_seconds() // 60),
        'login_url': conf.LOGIN_ABSOLUTE_URL,
    }
    try:
        send_mail(
            subject=render_to_string('emailotp/email/code_subject.txt', context).strip(),
            message=render_to_string('emailotp/email/code_body.txt', context),
            html_message=render_to_string(
                'emailotp/email/code_body.html', context
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception:
        otp.delete()
        logger.exception("emailotp: failed to send code to %s", email)
        return False

    AuthEvent.objects.create(kind=AuthEvent.CODE_SENT, email=email, ip=ip)
    return True


def notify_existing_account(email):
    """
    Anti-enumeration: when someone tries to register an address that already
    has an account, tell the mailbox owner rather than the screen.
    """
    context = {'site_name': conf.SITE_NAME, 'login_url': conf.LOGIN_ABSOLUTE_URL}
    send_mail(
        subject=render_to_string('emailotp/email/exists_subject.txt', context).strip(),
        message=render_to_string('emailotp/email/exists_body.txt', context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=True,
    )


def consume_otp(email, code, request, ip):
    """
    Check `code` against the newest live OTP for `email`.

    Returns (ok: bool, error_key: str|None). error_key is one of
    'expired', 'locked', 'wrong' — the caller maps it to a user-facing
    message so wording stays in the project, not the library.
    """
    from django.contrib.auth.hashers import check_password

    otp = (EmailOTP.objects
           .filter(email=email, used=False, expires_at__gt=timezone.now())
           .order_by('-created_at')
           .first())

    if otp is None:
        log(AuthEvent.VERIFY_FAIL, request, email, ip)
        return False, 'expired'

    if otp.attempts >= conf.MAX_VERIFY_ATTEMPTS:
        otp.used = True
        otp.save(update_fields=['used'])
        log(AuthEvent.VERIFY_FAIL, request, email, ip)
        return False, 'locked'

    if check_password(code, otp.code_hash):
        otp.used = True
        otp.save(update_fields=['used'])
        return True, None

    otp.attempts += 1
    otp.save(update_fields=['attempts'])
    log(AuthEvent.VERIFY_FAIL, request, email, ip)
    return False, 'wrong'

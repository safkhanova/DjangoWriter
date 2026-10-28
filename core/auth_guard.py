"""
Brute-force guard for emailotp's staff password step (/login/password/).

emailotp throttles code verification but not the password form, and it is kept
unmodified in this project, so the URL is wrapped here instead. Wrong passwords are
already logged by emailotp as AuthEvent.VERIFY_FAIL (with e-mail and IP); this wrapper
refuses further attempts once an IP or an account reaches its hourly budget.
"""

from datetime import timedelta

from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone

from emailotp import conf as otp_conf
from emailotp import services as otp_services
from emailotp import views as otp_views
from emailotp.models import AuthEvent

MAX_PASSWORD_FAILS_PER_ACCOUNT_1H = 10


def password_attempts_exhausted(email: str, ip: str | None) -> bool:
    since = timezone.now() - timedelta(hours=1)
    fails = AuthEvent.objects.filter(kind=AuthEvent.VERIFY_FAIL, created_at__gte=since)
    if ip and fails.filter(ip=ip).count() >= otp_conf.MAX_VERIFY_FAIL_PER_IP_1H:
        return True
    return bool(email) and fails.filter(email=email).count() >= MAX_PASSWORD_FAILS_PER_ACCOUNT_1H


def guarded_login_password(request):
    if request.method == "POST":
        email = request.session.get("emailotp_email", "")
        ip = otp_services.client_ip(request)
        if password_attempts_exhausted(email, ip):
            otp_services.log(AuthEvent.THROTTLED, request, email, ip)
            messages.error(request, "Çox sayda yanlış cəhd. Bir saat sonra yenidən cəhd edin.")
            return redirect("emailotp:login_password")
    return otp_views.login_password(request)

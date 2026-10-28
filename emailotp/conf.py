"""
emailotp/conf.py — all tunables, overridable from the project's settings.py.

Every name here reads an EMAILOTP_* setting and falls back to a sane default,
so a project can install the app with zero configuration and tighten things
later.
"""
from datetime import timedelta

from django.conf import settings

# --- OTP lifecycle ----------------------------------------------------------
OTP_LIFETIME = getattr(settings, 'EMAILOTP_LIFETIME', timedelta(minutes=10))
CODE_DIGITS = getattr(settings, 'EMAILOTP_CODE_DIGITS', 6)

# --- rate limits ------------------------------------------------------------
RESEND_COOLDOWN = getattr(settings, 'EMAILOTP_RESEND_COOLDOWN', timedelta(seconds=60))
MAX_PER_EMAIL_24H = getattr(settings, 'EMAILOTP_MAX_PER_EMAIL_24H', 5)
MAX_PER_IP_1H = getattr(settings, 'EMAILOTP_MAX_PER_IP_1H', 10)
MAX_VERIFY_ATTEMPTS = getattr(settings, 'EMAILOTP_MAX_VERIFY_ATTEMPTS', 5)
MAX_VERIFY_FAIL_PER_IP_1H = getattr(settings, 'EMAILOTP_MAX_VERIFY_FAIL_PER_IP_1H', 30)

# --- sessions ---------------------------------------------------------------
# Default session length comes from Django's SESSION_COOKIE_AGE; this is the
# longer one used when the user ticks "remember me".
REMEMBER_AGE = getattr(settings, 'EMAILOTP_REMEMBER_AGE', 60 * 60 * 24 * 30)

# --- behaviour --------------------------------------------------------------
# Staff accounts must also supply their password before the code step.
STAFF_REQUIRE_PASSWORD = getattr(settings, 'EMAILOTP_STAFF_REQUIRE_PASSWORD', True)

# Which User field holds the email address used for lookup. Projects that
# create users with username=email (the default here) leave this alone.
LOOKUP_FIELD = getattr(settings, 'EMAILOTP_LOOKUP_FIELD', 'username')

# Registration collects a name and password. Turn off for pure passwordless
# signup where the account has no usable password at all.
REGISTER_COLLECT_PASSWORD = getattr(settings, 'EMAILOTP_REGISTER_COLLECT_PASSWORD', True)
REGISTER_COLLECT_NAME = getattr(settings, 'EMAILOTP_REGISTER_COLLECT_NAME', True)

# Should verifying a code activate an account that already exists but is
# inactive? True keeps legacy rows working. False is safer: an inactive row
# may have been deactivated deliberately (a ban), and re-registering the
# address must not silently restore it.
ACTIVATE_EXISTING_INACTIVE = getattr(
    settings, 'EMAILOTP_ACTIVATE_EXISTING_INACTIVE', True)

# Log the user in immediately after they verify their registration code,
# instead of bouncing them to the login page to do it all again.
LOGIN_AFTER_REGISTER = getattr(settings, 'EMAILOTP_LOGIN_AFTER_REGISTER', True)

# --- captcha ----------------------------------------------------------------
# Requires django-recaptcha installed and RECAPTCHA_* keys configured.
USE_CAPTCHA = getattr(settings, 'EMAILOTP_USE_CAPTCHA', False)

# --- translation ------------------------------------------------------------
# Dotted path to a callable `(key, default) -> str`. This is the ONLY seam
# between this package and the host project's translation system. Leave unset
# and every string falls back to the English default written at its call site.
#
#     EMAILOTP_TRANSLATE = 'main.translation.translate'
TRANSLATE = getattr(settings, 'EMAILOTP_TRANSLATE', None)

# --- audit ------------------------------------------------------------------
# Days to keep AuthEvent rows. Used by the emailotp_cleanup command.
AUDIT_RETENTION_DAYS = getattr(settings, 'EMAILOTP_AUDIT_RETENTION_DAYS', 90)

# --- templates --------------------------------------------------------------
# Every shipped template extends this. Point it at your project's base
# template so the auth pages inherit your nav, styles and blocks.
BASE_TEMPLATE = getattr(settings, 'EMAILOTP_BASE_TEMPLATE', 'base.html')

# The block name inside BASE_TEMPLATE that page content goes into.
CONTENT_BLOCK = getattr(settings, 'EMAILOTP_CONTENT_BLOCK', 'content')

# Name shown in outgoing emails.
SITE_NAME = getattr(settings, 'EMAILOTP_SITE_NAME', 'this site')

# Absolute URL to the login page, used in the "account already exists" email.
LOGIN_ABSOLUTE_URL = getattr(settings, 'EMAILOTP_LOGIN_ABSOLUTE_URL', '')

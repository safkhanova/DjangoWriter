"""
Django settings.

The code is generic; everything that belongs to one particular site lives in the
*instance* folder (default `./instance`, git-ignored, see `instance.example/`):
`.env` with secrets and settings, the SQLite database, uploaded media, seed/import data,
and optional `templates/` / `static/` overrides.
"""

import os
from pathlib import Path
from urllib.parse import urlsplit

import environ
from django.templatetags.static import static
from django.urls import reverse_lazy

BASE_DIR = Path(__file__).resolve().parent.parent


def _instance_dir() -> Path:
    """
    Which site to run. One checkout can hold several instances (instanceAlice/, instanceBob/...):
    1. INSTANCE_DIR environment variable (absolute, or relative to the project);
    2. otherwise the folder named in the file `.instance` (git-ignored), e.g. "instanceAlice";
    3. otherwise ./instance.
    """
    name = os.environ.get("INSTANCE_DIR")
    marker = BASE_DIR / ".instance"
    if not name and marker.exists():
        name = marker.read_text(encoding="utf-8").strip()
    path = Path(name or "instance")
    return (path if path.is_absolute() else BASE_DIR / path).resolve()


INSTANCE_DIR = _instance_dir()

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    ADMIN_URL=(str, "admin/"),
    SITE_URL=(str, "http://127.0.0.1:8000"),
)
INSTANCE_CONFIGURED = (INSTANCE_DIR / ".env").exists()
environ.Env.read_env(INSTANCE_DIR / ".env")

DEBUG = env("DEBUG")
# Never a known fallback: a public key would let anyone forge sessions. Before the instance
# exists (first `manage.py init_instance`) a random throwaway key lets commands run;
# core.checks warns about it.
SECRET_KEY = env("SECRET_KEY", default=None) or (
    "dev-only-insecure-key-change-me" if DEBUG else None
) or (None if INSTANCE_CONFIGURED else __import__("secrets").token_urlsafe(50))
if not SECRET_KEY:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(f"SECRET_KEY must be set in {INSTANCE_DIR / '.env'} when DEBUG=False.")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

# Public base URL, used in e-mails (confirmation / unsubscribe links). It may include a
# path (https://example.com/writer) to serve the site under a sub-path of another domain;
# the reverse proxy must then strip that prefix before passing requests on.
SITE_URL = env("SITE_URL").rstrip("/")
_site_url = urlsplit(SITE_URL)
# Scheme + host only: reverse() already includes the sub-path, so absolute links are SITE_ORIGIN + reverse(...).
SITE_ORIGIN = f"{_site_url.scheme}://{_site_url.netloc}"
URL_PREFIX = _site_url.path.rstrip("/")  # "" when the site is at the domain root
if URL_PREFIX:
    FORCE_SCRIPT_NAME = URL_PREFIX
    # Own cookie names and paths, so this site never reads or overwrites the host site's cookies.
    SESSION_COOKIE_NAME = "dw_sessionid"
    CSRF_COOKIE_NAME = "dw_csrftoken"
    SESSION_COOKIE_PATH = CSRF_COOKIE_PATH = f"{URL_PREFIX}/"
# Short site label for the admin header and outgoing login e-mails, e.g. "example.com".
SITE_LABEL = env("SITE_LABEL", default=SITE_URL.split("://")[-1])
# Admin lives on a non-default path to reduce automated login attempts.
ADMIN_URL = env("ADMIN_URL")

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.forms",
    "unfold.contrib.reversion",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "reversion",
    "core",
    "content",
    "newsletter",
    "emailotp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.security.SecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.sessions.SessionActivityMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "reversion.middleware.RevisionMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # instance/templates (optional) overrides any project template with the same path
        "DIRS": [INSTANCE_DIR / "templates", BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
TEST_RUNNER = "tests.runner.SeededTestRunner"

# SQLite for local development, PostgreSQL in production via DATABASE_URL.
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{INSTANCE_DIR / 'db.sqlite3'}"),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# The interface and templates are written in Azerbaijani (see docs/ARCHITECTURE.md).
LANGUAGE_CODE = "az"
LANGUAGES = [("az", "Azərbaycan dili")]
# Azerbaijani strings for Unfold, which ships no az catalog.
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = env("TIME_ZONE", default="Asia/Baku")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# instance/static (optional) wins over project static files with the same path
STATICFILES_DIRS = [d for d in (INSTANCE_DIR / "static", BASE_DIR / "static") if d.is_dir()]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

MEDIA_URL = "media/"
MEDIA_ROOT = env("MEDIA_ROOT", default=str(INSTANCE_DIR / "media"))

# Uploads: photos straight from a phone can be large; they are re-encoded on save.
# Files are streamed separately; this limits the non-file part of a request body,
# which is what an anonymous attacker could inflate on the public forms.
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
# An article form sends ~20 fields per content block.
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
MAX_IMAGE_UPLOAD_MB = 15
MAX_DOCUMENT_UPLOAD_MB = 30

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- E-mail -----------------------------------------------------------------
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="webmaster@localhost")
# Max e-mails sent per `send_queued_emails` run (protects SMTP rate limits).
NEWSLETTER_BATCH_SIZE = env.int("NEWSLETTER_BATCH_SIZE", default=100)

# --- Login: e-mail OTP (emailotp app) ------------------------------------------
# Staff log in with password + a 6-digit code sent by e-mail (two factors).
# Usernames must equal the e-mail address (see docs/AUTH.md).
LOGIN_URL = "emailotp:login"
LOGIN_REDIRECT_URL = "admin:index"
LOGOUT_REDIRECT_URL = "core:home"
SESSION_COOKIE_AGE = 60 * 60 * 12
# Must stay database-backed: session revocation deletes rows (core/sessions.py).
SESSION_ENGINE = "django.contrib.sessions.backends.db"
# Flash messages in the session, not in a cookie that the host site could share.
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
EMAILOTP_SITE_NAME = SITE_LABEL
EMAILOTP_BASE_TEMPLATE = "site/auth_base.html"
EMAILOTP_LOGIN_ABSOLUTE_URL = f"{SITE_URL}/login/"
EMAILOTP_TRANSLATE = "core.translation.translate"
EMAILOTP_STAFF_REQUIRE_PASSWORD = True
EMAILOTP_ACTIVATE_EXISTING_INACTIVE = False
EMAILOTP_REGISTER_COLLECT_PASSWORD = False
EMAILOTP_REMEMBER_AGE = 60 * 60 * 24 * 30
EMAILOTP_IP_HEADER = env("EMAILOTP_IP_HEADER", default="HTTP_X_REAL_IP")

# Shared by all gunicorn workers, so per-IP rate limits are not multiplied by the worker count.
# Table created by `manage.py createcachetable` (see docs/DEPLOY.md).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "cache_table",
    }
}

# Content-Security-Policy for public pages (core/security.py). Extra script origins,
# e.g. an analytics provider: CSP_EXTRA_SCRIPT_SRC=https://plausible.io
CSP_EXTRA_SCRIPT_SRC = env.list("CSP_EXTRA_SCRIPT_SRC", default=[])

# --- Security (production) ----------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
    CSRF_COOKIE_HTTPONLY = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# --- Admin (Unfold) -----------------------------------------------------------
UNFOLD = {
    "SITE_TITLE": "Sayt idarəetməsi",
    "SITE_HEADER": "Sayt idarəetməsi",
    "SITE_SUBHEADER": SITE_LABEL,
    "SITE_URL": f"{URL_PREFIX}/",
    "SITE_SYMBOL": "edit_note",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "SHOW_BACK_BUTTON": True,
    "DASHBOARD_CALLBACK": "core.dashboard.dashboard_callback",
    "STYLES": [lambda request: static("admin/site_admin.css")],
    "SCRIPTS": [lambda request: static("admin/block_fields.js")],
    "COLORS": {
        "primary": {
            "50": "oklch(97% .02 170)",
            "100": "oklch(94% .04 170)",
            "200": "oklch(88% .07 170)",
            "300": "oklch(80% .09 170)",
            "400": "oklch(68% .1 170)",
            "500": "oklch(56% .1 170)",
            "600": "oklch(47% .09 170)",
            "700": "oklch(40% .08 170)",
            "800": "oklch(33% .06 170)",
            "900": "oklch(27% .05 170)",
            "950": "oklch(20% .04 170)",
        },
    },
    "SIDEBAR": {
        "show_search": False,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Məzmun",
                "items": [
                    {
                        "title": "Yazılar",
                        "icon": "article",
                        "link": reverse_lazy("admin:content_article_changelist"),
                        "permission": lambda r: r.user.has_perm("content.view_article"),
                    },
                    {
                        "title": "Bölmələr",
                        "icon": "view_agenda",
                        "link": reverse_lazy("admin:content_section_changelist"),
                        "permission": lambda r: r.user.has_perm("content.view_section"),
                    },
                    {
                        "title": "Növlər",
                        "icon": "label",
                        "link": reverse_lazy("admin:content_category_changelist"),
                        "permission": lambda r: r.user.has_perm("content.view_category"),
                    },
                    {
                        "title": "Etiketlər",
                        "icon": "sell",
                        "link": reverse_lazy("admin:content_tag_changelist"),
                        "permission": lambda r: r.user.has_perm("content.view_tag"),
                    },
                ],
            },
            {
                "title": "Ana səhifə və dizayn",
                "items": [
                    {
                        "title": "Hero (giriş bloku)",
                        "icon": "web_asset",
                        "link": reverse_lazy("admin:core_hero_changelist"),
                        "permission": lambda r: r.user.has_perm("core.view_hero"),
                    },
                    {
                        "title": "Sayt ayarları",
                        "icon": "tune",
                        "link": reverse_lazy("admin:core_sitesettings_changelist"),
                        "permission": lambda r: r.user.has_perm("core.view_sitesettings"),
                    },
                    {
                        "title": "Sosial şəbəkələr",
                        "icon": "share",
                        "link": reverse_lazy("admin:core_sociallink_changelist"),
                        "permission": lambda r: r.user.has_perm("core.view_sociallink"),
                    },
                ],
            },
            {
                "title": "Əlaqə və abunəçilər",
                "items": [
                    {
                        "title": "Mesajlar",
                        "icon": "mail",
                        "link": reverse_lazy("admin:core_contactmessage_changelist"),
                        "permission": lambda r: r.user.has_perm("core.view_contactmessage"),
                        "badge": "core.dashboard.unread_messages_badge",
                    },
                    {
                        "title": "Mesaj mövzuları",
                        "icon": "list",
                        "link": reverse_lazy("admin:core_contacttopic_changelist"),
                        "permission": lambda r: r.user.has_perm("core.view_contacttopic"),
                    },
                    {
                        "title": "Abunəçilər",
                        "icon": "group",
                        "link": reverse_lazy("admin:newsletter_subscriber_changelist"),
                        "permission": lambda r: r.user.has_perm("newsletter.view_subscriber"),
                    },
                    {
                        "title": "Göndərilən bülletenlər",
                        "icon": "send",
                        "link": reverse_lazy("admin:newsletter_newsletterissue_changelist"),
                        "permission": lambda r: r.user.has_perm("newsletter.view_newsletterissue"),
                    },
                ],
            },
            {
                "title": "Hesab və təhlükəsizlik",
                "items": [
                    {
                        "title": "Aktiv sessiyalar",
                        "icon": "devices",
                        "link": reverse_lazy("admin:core_usersession_changelist"),
                        "permission": lambda r: r.user.is_staff,
                    },
                ],
            },
            {
                "title": "Texniki (yalnız administrator)",
                "items": [
                    {
                        "title": "İstifadəçilər",
                        "icon": "person",
                        "link": reverse_lazy("admin:auth_user_changelist"),
                        "permission": lambda r: r.user.is_superuser,
                    },
                    {
                        "title": "Qruplar",
                        "icon": "groups",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                        "permission": lambda r: r.user.is_superuser,
                    },
                    {
                        "title": "E-poçt növbəsi",
                        "icon": "outbox",
                        "link": reverse_lazy("admin:newsletter_outgoingemail_changelist"),
                        "permission": lambda r: r.user.is_superuser,
                    },
                ],
            },
        ],
    },
}

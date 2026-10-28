# django-emailotp — integration guide

Passwordless authentication for Django: the user types their email address,
receives a numeric code, and is signed in. Staff accounts can additionally be
required to enter their password first.

Each project keeps its own database and its own users. This package shares
**code**, not identities — someone registered on site A has no account on
site B.

---

## 1. Install

Copy the `emailotp/` directory into the project root, next to `manage.py` and
your other apps:

```
myproject/
├── manage.py
├── myproject/          # settings, urls
├── main/               # your app
└── emailotp/           # <- copied in
```

Django finds it because the project root is already on `sys.path`. No pip, no
packaging.

The alternative is `pip install -e /path/to/django-emailotp`, which keeps one
shared copy across projects. The trade-off: an edit for one site changes every
site pointing at it, and the code doesn't appear in your project tree. For a
project you're still actively changing, copying is usually the better trade.

### settings.py

```python
INSTALLED_APPS = [
    ...
    'main',
    'emailotp',
]

MIDDLEWARE = [
    ...
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    ...
]

LOGIN_URL = 'emailotp:login'
LOGIN_REDIRECT_URL = 'main:home'      # where signed-in users land
LOGOUT_REDIRECT_URL = 'main:home'

SESSION_COOKIE_AGE = 60 * 60 * 24     # 24h; "remember me" overrides per-session

EMAILOTP_SITE_NAME = 'Example'
EMAILOTP_BASE_TEMPLATE = 'main/base.html'
EMAILOTP_LOGIN_ABSOLUTE_URL = 'https://example.com/login/'

# email must work — the codes go out over SMTP
DEFAULT_FROM_EMAIL = 'noreply@example.com'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
```

`django.contrib.messages` and `django.contrib.sessions` must be installed, with
their middleware **and** the messages context processor. Without the context
processor every error message renders as nothing and the pages appear to do
nothing when you submit a wrong code.

### urls.py

```python
path('', include('emailotp.urls')),
```

If another include also matches the empty prefix (e.g. `include('main.urls')`),
put `emailotp.urls` **first** — Django takes the first match.

### Then

```bash
python manage.py migrate
python manage.py check
```

---

## 2. The flows

### Registration

```
GET  /register/          form: name, email, [password ×2], [captcha]
POST /register/          -> code emailed, nothing written to the user table
GET  /register/verify/   form: the code
POST /register/verify/   -> account created, user logged in
POST /register/resend/   -> new code, rate-limited
```

The account row is **not created until the code is confirmed**. Name and
password are parked in the session (password as a hash, never plaintext) and
the user is created on verification. An abandoned registration leaves nothing
behind and cannot squat someone else's address.

### Login, non-staff

```
GET  /login/             form: email, remember-me, [captcha]
POST /login/             -> code emailed
GET  /login/verify/      form: the code
POST /login/verify/      -> logged in
POST /login/resend/      -> new code, rate-limited
```

### Login, staff

```
POST /login/             -> redirected to the password step
GET  /login/password/    form: password
POST /login/password/    -> password checked, then code emailed
POST /login/verify/      -> logged in
```

Staff go through `authenticate()`, so django-axes (if installed) sees failed
password attempts and can lock the account.

### Session keys

`emailotp_email`, `emailotp_stage` (`password` | `code`), `emailotp_flow`
(`register` | `login`), `emailotp_remember`, `emailotp_pending`. All cleared on
success. Each view guards on stage and flow, so a half-finished registration
can't be walked into via the login verify page.

---

## 3. Settings

All optional. Defaults shown.

### OTP lifecycle

| Setting | Default | Purpose |
|---|---|---|
| `EMAILOTP_LIFETIME` | `timedelta(minutes=10)` | how long a code stays valid |
| `EMAILOTP_CODE_DIGITS` | `6` | code length |

### Rate limits

| Setting | Default | Purpose |
|---|---|---|
| `EMAILOTP_RESEND_COOLDOWN` | `timedelta(seconds=60)` | minimum gap between codes per address |
| `EMAILOTP_MAX_PER_EMAIL_24H` | `5` | codes per address per day |
| `EMAILOTP_MAX_PER_IP_1H` | `10` | codes per IP per hour |
| `EMAILOTP_MAX_VERIFY_ATTEMPTS` | `5` | wrong guesses before a code dies |
| `EMAILOTP_MAX_VERIFY_FAIL_PER_IP_1H` | `30` | wrong guesses per IP per hour |

How these compose: one code allows 5 guesses; requesting a fresh code resets
that counter, and `MAX_PER_EMAIL_24H` caps it at 5 codes per day. So an
attacker targeting one address gets 25 guesses per day against a 1,000,000
space. The per-IP verify limit is what stops one host spreading guesses across
thousands of addresses — a case no per-address limit can catch.

Keep the per-IP limit generous. Mobile and office networks put many people
behind one address, and the per-code counter does the real anti-guessing work.

### Behaviour

| Setting | Default | Purpose |
|---|---|---|
| `EMAILOTP_STAFF_REQUIRE_PASSWORD` | `True` | staff enter a password before the code |
| `EMAILOTP_LOOKUP_FIELD` | `'username'` | User field holding the email address |
| `EMAILOTP_REGISTER_COLLECT_NAME` | `True` | ask for a name at signup |
| `EMAILOTP_REGISTER_COLLECT_PASSWORD` | `True` | ask for a password at signup |
| `EMAILOTP_LOGIN_AFTER_REGISTER` | `True` | sign in on registration verify |
| `EMAILOTP_ACTIVATE_EXISTING_INACTIVE` | `True` | verifying can reactivate an inactive row |
| `EMAILOTP_REMEMBER_AGE` | `2592000` (30d) | session length with "remember me" |

### Other

| Setting | Default | Purpose |
|---|---|---|
| `EMAILOTP_USE_CAPTCHA` | `False` | enable django-recaptcha on the entry forms |
| `EMAILOTP_TRANSLATE` | `None` | dotted path to a translation callable |
| `EMAILOTP_AUDIT_RETENTION_DAYS` | `90` | audit rows kept by the cleanup command |
| `EMAILOTP_IP_HEADER` | `'HTTP_X_REAL_IP'` | request header holding the client IP |
| `EMAILOTP_BASE_TEMPLATE` | `'base.html'` | template every page extends |
| `EMAILOTP_SITE_NAME` | `'this site'` | name used in outgoing email |
| `EMAILOTP_LOGIN_ABSOLUTE_URL` | `''` | full login URL for the "account exists" email |

### Settings worth changing on day one

**`EMAILOTP_ACTIVATE_EXISTING_INACTIVE = False`** — with the default `True`, a
user an admin deactivated as a ban can re-register their address and be
reactivated. Set it to `False` unless you have legacy inactive rows that need
activating.

**`EMAILOTP_REGISTER_COLLECT_PASSWORD = False`** — if login is passwordless,
collecting a password at signup is asking for something never used. Staff still
need passwords, but staff are created via `createsuperuser` or the admin, not
this form.

**`EMAILOTP_BASE_TEMPLATE`** — must point at a real template of yours, or the
pages render bare.

---

## 4. Templates and styling

The package ships nine templates under `emailotp/templates/emailotp/`. Any of
them can be overridden by creating a file at the **same path** in a directory
Django searches first — either your project's `templates/` dir (listed in
`TEMPLATES[0]['DIRS']`) or another app's `templates/`, if that app comes before
`emailotp` in `INSTALLED_APPS`.

```
main/templates/emailotp/login.html      # overrides the package's login.html
```

The most useful override is `base.html`, which is where the CSS and JS get
pulled in:

```django
{% extends base_template %}
{% load static %}

{% block extrahead %}
  <link rel="stylesheet" href="{% static 'emailotp/css/emailotp.css' %}">
{% endblock %}

{% block extra_js %}
  <script src="{% static 'emailotp/js/emailotp.js' %}"></script>
{% endblock %}
```

Your `EMAILOTP_BASE_TEMPLATE` must define blocks with those names, or the
stylesheet is silently dropped and the pages render unstyled.

Markup uses `emailotp-*` class names and no inline styles. Ship your own CSS at
`main/static/main/css/emailotp.css` (site-specific look) or
`emailotp/static/emailotp/css/emailotp.css` (travels with the package).

Remember `python manage.py collectstatic` on deploy — forgetting it is the
usual cause of "the auth pages lost their styling in production".

---

## 5. Translation and the `{% t %}` tag

The package has exactly one seam into your translation system: a setting
holding a dotted path to a callable `(key, default) -> str`.

```python
EMAILOTP_TRANSLATE = 'main.translation.translate'
```

Leave it unset and every string falls back to the English default written
inline at its call site. The package works untranslated; it never imports your
app.

### How the tag works

In templates:

```django
{% load emailotp_tags %}
{% t "emailotp.login.title" default="Sign in" %}
```

In Python (`views.py`, `forms.py`):

```python
tr('emailotp.msg.code_wrong', 'That code is not correct.')
tr_lazy('emailotp.form.email', 'Email')   # for form labels
```

Both route through `emailotp/translation.py`, which imports your callable once
and caches it. If the callable raises, `tr()` returns the English default
rather than breaking a login page.

`tr_lazy` exists because form fields are built at import time, before a request
exists and before the active language is known. Using `tr()` for a label would
freeze whatever language happened to be active at startup.

### A DB-backed backend

If your project stores translations in the database:

```python
# main/translation.py
from django.conf import settings
from django.utils.translation import get_language
from .models import TranslationValue


def translate(key, default=''):
    fallback = getattr(settings, 'TRANSLATION_FALLBACK_LANGUAGE', 'en')
    active = get_language() or fallback
    languages = [active] + ([fallback] if fallback != active else [])

    rows = {
        v.language: v.text
        for v in TranslationValue.objects.filter(
            translation_key__key=key, language__in=languages)
        if v.text
    }
    for lang in languages:
        if rows.get(lang):
            return rows[lang]
    return default or key
```

`TRANSLATION_FALLBACK_LANGUAGE` is the single point that decides the fallback
language for the whole project — change it per project (`az`, `en`, `it`) and
every lookup follows, in templates and Python alike.

### A gettext backend

Nothing stops you pointing the setting at Django's own machinery:

```python
# main/translation.py
from django.utils.translation import gettext

def translate(key, default=''):
    result = gettext(default or key)
    return result
```

### Key namespaces

- `emailotp.msg.*` — messages raised from `views.py`
- `emailotp.form.*` — field labels and validation errors from `forms.py`
- `emailotp.<page>.*` — page text from templates
- `emailotp.email.*` — outgoing email subjects and bodies

45 keys in total. `emailotp_translations.py` in the package holds az/en/it for
all of them, ready to load into a DB-backed system.

### Two traps

**A blank translation is worse than a missing one.** If your backend filters on
truthiness (`if v.text`), a whitespace-only row falls through to the fallback
language — so a deliberately empty string prints the fallback language's text
mid-sentence. Use `"."` or a real string, never `""`.

**Template scanners must not touch package templates.** If your project has an
admin tool that scans templates for `{% t %}` tags and writes each `default=`
into the primary-language column, pointing it at `emailotp/` will write English
into that column, because the package's defaults are English by design.
Exclude the app from the scan, and protect `emailotp.*` keys from any
"delete orphaned keys" step — the `emailotp.form.*` keys live in `forms.py`,
not in a template, so a template scanner can never see them and will always
consider them orphaned.

---

## 6. Proxy configuration — required in production

Rate limits are keyed on the client IP. Behind a reverse proxy, Django sees
`127.0.0.1` unless the proxy says otherwise.

This package trusts `X-Real-IP` and deliberately ignores `X-Forwarded-For`.
nginx's `proxy_set_header X-Real-IP $remote_addr` **overwrites** whatever the
client sent, so it can't be forged. `$proxy_add_x_forwarded_for` **appends** to
a client-supplied header, leaving its leftmost value attacker-controlled — and
an IP limit keyed on a spoofable value is worse than no limit, because it
reads like protection in review.

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

If a CDN sits in front of nginx (Cloudflare, a load balancer), `X-Real-IP` now
holds the *edge's* address, not the visitor's — set `EMAILOTP_IP_HEADER` to
whatever your provider sets (`HTTP_CF_CONNECTING_IP` for Cloudflare).

If you use django-axes, it does its own IP detection via django-ipware and may
read `X-Forwarded-For` by default:

```python
AXES_IPWARE_META_PRECEDENCE_ORDER = ('HTTP_X_REAL_IP',)
```

---

## 7. Django admin

Django's admin has its own password login form that bypasses this flow
entirely. To close it, in the root `urls.py` **before** `urlpatterns`:

```python
from django.contrib.admin.views.decorators import staff_member_required
admin.site.login = staff_member_required(admin.site.login, login_url='emailotp:login')
```

Optionally also at the proxy, as defence in depth:

```nginx
location = /admin/login/ { return 302 /login/; }
```

Use `location =` (exact match) — a prefix match would swallow anything starting
with that string.

`/admin/` itself keeps working: it checks the existing session, which staff
already have once they've come through this flow.

---

## 8. The username convention

By default the package looks users up as `User.objects.filter(username=email)`
and creates accounts with `username=email`.

If a project already has non-email usernames, those users **cannot log in** —
the form only accepts an email and the lookup won't match. Find them:

```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
for u, e in get_user_model().objects.values_list('username', 'email'):
    if '@' not in u:
        print('BROKEN:', u, '| email on file:', e or '(none)')
"
```

Fix each by setting `username` to the email address. Rows with no email on file
can't be fixed without asking the person.

The alternative is `EMAILOTP_LOOKUP_FIELD = 'email'`, but note Django does not
enforce uniqueness on `email` — add that constraint yourself before relying
on it, or two accounts can share an address and the lookup becomes ambiguous.

---

## 9. Maintenance

Both tables grow without bound. Run nightly:

```
0 4 * * * cd /path/to/project && venv/bin/python manage.py emailotp_cleanup
```

`--dry-run` reports without deleting; `--audit-days N` overrides retention.

The admin has read-only views of `EmailOTP` and `AuthEvent`. `AuthEvent` is the
audit trail — `code_requested`, `code_sent`, `verify_ok`, `verify_fail`,
`throttled` — and also backs the per-IP verify throttle, so don't prune it
more aggressively than one hour.

---

## 10. Deployment checklist

```bash
git pull
pip install -r requirements.txt
python manage.py check
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart <gunicorn-service>
```

Then verify:

```bash
curl -sI https://example.com/login/ | head -1                              # 200
curl -sI https://example.com/admin/login/ | head -1                        # 302
curl -sI https://example.com/static/emailotp/css/emailotp.css | head -1    # 200
```

And in a browser, **before closing your SSH session**: log in with your own
staff account end to end. If SMTP is misconfigured, no code arrives, and with
`/admin/login/` redirected you'd have locked yourself out of both the site and
the admin.

---

## 11. What this deliberately does not do

**Single sign-on.** Users are per-project. Sharing identities across sites
needs a central auth service and OAuth/OIDC — a different and much larger
piece of work.

**Hide which addresses are staff.** Staff go to a password page while everyone
else goes to the code page, so the first step reveals staff addresses. Closing
that would mean asking everyone for a password, which defeats the purpose.

**Rate-limit at the edge.** These limits are application-level. A serious flood
should be stopped by the proxy before it reaches Django.

**Tell the user whether an address exists.** Unknown addresses, throttled
requests, and registering an address that already has an account all show the
same screen. That ambiguity is deliberate, but it does mean someone who
mistypes their address gets a confusing dead end — worth a line on the verify
page such as "Didn't get a code? Check the address and look in spam."
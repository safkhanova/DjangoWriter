"""
emailotp/views.py

Registration:  /register/ -> code emailed -> /register/verify/ -> logged in
Login (user):  /login/    -> code emailed -> /login/verify/     -> logged in
Login (staff): /login/    -> /login/password/ -> code -> /login/verify/

Session keys used: emailotp_email, emailotp_stage, emailotp_remember,
emailotp_flow ('register' | 'login').
"""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch
from django.views.decorators.http import require_POST

from . import conf, services
from .translation import tr
from .forms import LoginForm, LoginPasswordForm, RegisterForm, VerifyForm
from .models import AuthEvent

User = get_user_model()

# auth_login() needs an explicit backend when we bypass authenticate()
DEFAULT_BACKEND = 'django.contrib.auth.backends.ModelBackend'

K = 'emailotp.msg.'


def _verify_error(err):
    return {
        'expired': lambda: tr(
            K + 'code_expired', 'That code is no longer valid. Request a new one.'),
        'locked': lambda: tr(
            K + 'too_many_wrong', 'Too many wrong attempts. Request a new code.'),
        'wrong': lambda: tr(K + 'code_wrong', 'That code is not correct.'),
    }[err]()


def _create_or_activate(email, pending):
    """
    Create the account now that the address is proven.

    Three cases:
      * no row exists           -> create it, active
      * an inactive row exists  -> activate it and apply the new details,
                                   but only if ACTIVATE_EXISTING_INACTIVE
      * an active row exists    -> return it untouched

    The last case is the important one. The register view never issues a
    code for an address that already has an active account, so this should
    be unreachable — but if it ever becomes reachable, overwriting a live
    account's name and password would be an account takeover. Refusing to
    write is the safe default rather than a promise made elsewhere.
    """
    fields = {}
    if conf.REGISTER_COLLECT_NAME and pending.get('name'):
        fields['first_name'] = pending['name']

    try:
        with transaction.atomic():
            user, created = User.objects.get_or_create(
                **{conf.LOOKUP_FIELD: email},
                defaults={'email': email, 'is_active': True, **fields},
            )
    except IntegrityError:  # pragma: no cover - concurrent create
        user = User.objects.filter(**{conf.LOOKUP_FIELD: email}).first()
        created = False
        if user is None:
            return None

    if not created:
        if user.is_active:
            # never overwrite a live account
            return user
        if not conf.ACTIVATE_EXISTING_INACTIVE:
            # the row may have been deactivated deliberately (a ban);
            # re-registering must not silently restore it
            return None
        user.is_active = True
        for k, v in fields.items():
            setattr(user, k, v)

    if pending.get('password_hash'):
        user.password = pending['password_hash']
    elif created:
        user.set_unusable_password()

    user.save()
    return user


# --- helpers ----------------------------------------------------------------

def _redirect_after_login(request):
    target = settings.LOGIN_REDIRECT_URL
    try:
        return redirect(target)
    except NoReverseMatch:  # pragma: no cover
        return redirect('/')


def _clear_flow(request):
    for key in ('emailotp_email', 'emailotp_stage', 'emailotp_remember',
                'emailotp_flow', 'emailotp_pending'):
        request.session.pop(key, None)


def _finish_login(request, user, remember=False):
    """Log in, set session length, clear flow state."""
    _clear_flow(request)
    auth_login(request, user, backend=DEFAULT_BACKEND)
    request.session.set_expiry(
        conf.REMEMBER_AGE if remember else settings.SESSION_COOKIE_AGE
    )


def _send_failed(request):
    messages.error(request, tr(
        K + 'send_failed',
        "We couldn't send the code right now. Please try again in a moment."))


def _start_code_stage(request, email, ip, flow):
    """Move to the code step, sending a code unless throttled."""
    request.session['emailotp_stage'] = 'code'
    request.session['emailotp_flow'] = flow
    if services.sending_allowed(email, ip):
        if not services.issue_otp(email, ip):
            _send_failed(request)
    else:
        services.log(AuthEvent.THROTTLED, request, email, ip)


def _ctx(extra=None):
    base = {'base_template': conf.BASE_TEMPLATE}
    if extra:
        base.update(extra)
    return base


# --- registration -----------------------------------------------------------

def register(request):
    if request.user.is_authenticated:
        return _redirect_after_login(request)

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        ip = services.client_ip(request)
        services.log(AuthEvent.CODE_REQUESTED, request, email, ip)

        existing = User.objects.filter(**{conf.LOOKUP_FIELD: email}).first()

        # No account row is created here. The details are parked in the
        # session and the user is only created once the code is confirmed,
        # so an abandoned registration leaves nothing behind and cannot
        # squat someone else's address.
        pending = {}
        if conf.REGISTER_COLLECT_NAME:
            pending['name'] = form.cleaned_data['name']
        if conf.REGISTER_COLLECT_PASSWORD:
            # hashed, never plaintext: the session may be stored in the DB
            # or a cookie, neither of which should ever hold a password
            pending['password_hash'] = make_password(form.cleaned_data['password1'])
        request.session['emailotp_pending'] = pending

        inactive_is_blocked = (
            existing and not existing.is_active
            and not conf.ACTIVATE_EXISTING_INACTIVE
        )
        if existing and (existing.is_active or inactive_is_blocked):
            # Never reveal on screen that the account exists. Inactive rows
            # are deliberate blocks when activation is disabled: do not send
            # them a new registration OTP or reactivate them publicly.
            if existing.is_active:
                services.notify_existing_account(email)
            request.session['emailotp_stage'] = 'code'
            request.session['emailotp_flow'] = 'register'
        elif services.sending_allowed(email, ip):
            _start_code_stage(request, email, ip, 'register')
        else:
            services.log(AuthEvent.THROTTLED, request, email, ip)
            request.session['emailotp_stage'] = 'code'
            request.session['emailotp_flow'] = 'register'

        request.session['emailotp_email'] = email
        return redirect('emailotp:register_verify')

    return render(request, 'emailotp/register.html', _ctx({'form': form}))


def register_verify(request):
    email = request.session.get('emailotp_email')
    if not email or request.session.get('emailotp_flow') != 'register':
        return redirect('emailotp:register')

    form = VerifyForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ip = services.client_ip(request)

        if not services.verify_allowed(ip):
            services.log(AuthEvent.THROTTLED, request, email, ip)
            messages.error(request, tr(K + 'throttled', 'Too many attempts. Try again later.'))
            return render(request, 'emailotp/register_verify.html',
                          _ctx({'form': form, 'email': email}))

        ok, err = services.consume_otp(email, form.cleaned_data['code'], request, ip)
        if ok:
            pending = request.session.get('emailotp_pending') or {}
            user = _create_or_activate(email, pending)
            if user is None:
                _clear_flow(request)
                return redirect('emailotp:register')

            services.log(AuthEvent.VERIFY_OK, request, email, ip)

            if conf.LOGIN_AFTER_REGISTER:
                _finish_login(request, user)
                return _redirect_after_login(request)

            _clear_flow(request)
            messages.success(request, tr(K + 'email_confirmed', 'Email confirmed. You can now sign in.'))
            return redirect('emailotp:login')

        messages.error(request, _verify_error(err))

    return render(request, 'emailotp/register_verify.html',
                  _ctx({'form': form, 'email': email}))


@require_POST
def register_resend(request):
    email = request.session.get('emailotp_email')
    if not email or request.session.get('emailotp_flow') != 'register':
        return redirect('emailotp:register')

    ip = services.client_ip(request)
    existing = User.objects.filter(**{conf.LOOKUP_FIELD: email}).first()
    can_register = (
        existing is None
        or (not existing.is_active and conf.ACTIVATE_EXISTING_INACTIVE)
    )
    if can_register and services.sending_allowed(email, ip):
        if not services.issue_otp(email, ip):
            _send_failed(request)
            return redirect('emailotp:register_verify')
    else:
        services.log(AuthEvent.THROTTLED, request, email, ip)

    # Same message whether sent or throttled.
    messages.info(request, tr(K + 'resent', 'If the address is correct, a new code has been sent.'))
    return redirect('emailotp:register_verify')


# --- login ------------------------------------------------------------------

def login_start(request):
    if request.user.is_authenticated:
        return _redirect_after_login(request)

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        ip = services.client_ip(request)
        services.log(AuthEvent.CODE_REQUESTED, request, email, ip)

        request.session['emailotp_email'] = email
        request.session['emailotp_remember'] = form.cleaned_data['remember']

        user = services.get_user_by_email(email)

        if user and user.is_staff and conf.STAFF_REQUIRE_PASSWORD:
            request.session['emailotp_stage'] = 'password'
            request.session['emailotp_flow'] = 'login'
            return redirect('emailotp:login_password')

        if user:
            _start_code_stage(request, email, ip, 'login')
        else:
            # Unknown address: identical screen, no email sent.
            request.session['emailotp_stage'] = 'code'
            request.session['emailotp_flow'] = 'login'

        return redirect('emailotp:login_verify')

    return render(request, 'emailotp/login.html', _ctx({'form': form}))


def login_password(request):
    email = request.session.get('emailotp_email')
    if not email or request.session.get('emailotp_stage') != 'password':
        return redirect('emailotp:login')

    form = LoginPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ip = services.client_ip(request)
        # go through authenticate() so django-axes (if installed) sees failures
        user = authenticate(request, username=email,
                            password=form.cleaned_data['password'])
        if user is not None and user.is_staff:
            _start_code_stage(request, email, ip, 'login')
            return redirect('emailotp:login_verify')

        services.log(AuthEvent.VERIFY_FAIL, request, email, ip)
        messages.error(request, tr(K + 'password_wrong', 'That password is not correct.'))

    return render(request, 'emailotp/login_password.html',
                  _ctx({'form': form, 'email': email}))


def login_verify(request):
    email = request.session.get('emailotp_email')
    if not email or request.session.get('emailotp_stage') != 'code' \
            or request.session.get('emailotp_flow') != 'login':
        return redirect('emailotp:login')

    form = VerifyForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ip = services.client_ip(request)

        if not services.verify_allowed(ip):
            services.log(AuthEvent.THROTTLED, request, email, ip)
            messages.error(request, tr(K + 'throttled', 'Too many attempts. Try again later.'))
            return render(request, 'emailotp/login_verify.html',
                          _ctx({'form': form, 'email': email}))

        ok, err = services.consume_otp(email, form.cleaned_data['code'], request, ip)
        if ok:
            user = services.get_user_by_email(email)
            if user is None:
                _clear_flow(request)
                return redirect('emailotp:login')

            remember = request.session.get('emailotp_remember', False)
            services.log(AuthEvent.VERIFY_OK, request, email, ip)
            _finish_login(request, user, remember)
            return _redirect_after_login(request)

        messages.error(request, _verify_error(err))

    return render(request, 'emailotp/login_verify.html',
                  _ctx({'form': form, 'email': email}))


@require_POST
def login_resend(request):
    email = request.session.get('emailotp_email')
    # the flow check stops a registration session from mailing a login code
    # to the owner of an existing account
    if not email or request.session.get('emailotp_stage') != 'code' \
            or request.session.get('emailotp_flow') != 'login':
        return redirect('emailotp:login')

    ip = services.client_ip(request)
    user = services.get_user_by_email(email)
    if user and services.sending_allowed(email, ip):
        if not services.issue_otp(email, ip):
            _send_failed(request)
            return redirect('emailotp:login_verify')
    else:
        services.log(AuthEvent.THROTTLED, request, email, ip)

    messages.info(request, tr(K + 'resent', 'If the address is correct, a new code has been sent.'))
    return redirect('emailotp:login_verify')

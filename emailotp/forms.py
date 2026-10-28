"""
emailotp/forms.py

Captcha is optional. Set EMAILOTP_USE_CAPTCHA = True and install
django-recaptcha to enable it on the register and login-start forms.
"""
from django import forms
from django.contrib.auth.password_validation import validate_password
from . import conf
from .translation import tr, tr_lazy

K = 'emailotp.form.'


def _captcha_field(action):
    """Return a ReCaptchaField, or None when captcha is off/unavailable."""
    if not conf.USE_CAPTCHA:
        return None
    try:
        from django_recaptcha.fields import ReCaptchaField
        from django_recaptcha.widgets import ReCaptchaV3
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "EMAILOTP_USE_CAPTCHA is True but django-recaptcha is not "
            "installed. Run `pip install django-recaptcha` or set "
            "EMAILOTP_USE_CAPTCHA = False."
        ) from exc
    return ReCaptchaField(widget=ReCaptchaV3(action=action))


class _CaptchaMixin:
    """Adds the captcha field at init time so the setting is read late."""
    captcha_action = 'submit'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = _captcha_field(self.captcha_action)
        if field is not None:
            self.fields['captcha'] = field


class RegisterForm(_CaptchaMixin, forms.Form):
    captcha_action = 'register'

    email = forms.EmailField(label=tr_lazy(K + 'email', 'Email'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if conf.REGISTER_COLLECT_NAME:
            self.fields['name'] = forms.CharField(max_length=150, label=tr_lazy(K + 'name', 'Name'))
        if conf.REGISTER_COLLECT_PASSWORD:
            self.fields['password1'] = forms.CharField(
                widget=forms.PasswordInput, label=tr_lazy(K + 'password', 'Password'))
            self.fields['password2'] = forms.CharField(
                widget=forms.PasswordInput, label=tr_lazy(K + 'password2', 'Password (again)'))
        # keep email first, captcha last
        order = ['name', 'email', 'password1', 'password2', 'captcha']
        self.order_fields([f for f in order if f in self.fields])

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def clean(self):
        cleaned = super().clean()
        if not conf.REGISTER_COLLECT_PASSWORD:
            return cleaned
        p1, p2 = cleaned.get('password1'), cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', tr(
                K + 'password_mismatch', 'The two passwords do not match.'))
        elif p1:
            validate_password(p1)
        return cleaned


class VerifyForm(forms.Form):
    code = forms.CharField(
        min_length=conf.CODE_DIGITS,
        max_length=conf.CODE_DIGITS,
        label=tr_lazy(K + 'code', 'Code'),
    )

    def clean_code(self):
        code = self.cleaned_data['code'].strip()
        if not code.isdigit():
            raise forms.ValidationError(
                tr(K + 'code_digits', 'The code is {n} digits.').format(
                    n=conf.CODE_DIGITS)
            )
        return code


class LoginForm(_CaptchaMixin, forms.Form):
    captcha_action = 'login'

    email = forms.EmailField(label=tr_lazy(K + 'email', 'Email'))
    remember = forms.BooleanField(required=False, label=tr_lazy(K + 'remember', 'Remember me'))

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


class LoginPasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, label=tr_lazy(K + 'password', 'Password'))

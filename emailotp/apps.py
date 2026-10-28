from django.apps import AppConfig


class EmailOTPConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'emailotp'
    verbose_name = 'Email OTP authentication'

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Sayt'

    def ready(self):
        from . import checks, sessions  # noqa: F401  (registers system checks, login/logout receivers)

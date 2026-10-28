from django.conf import settings
from django.core.checks import Warning, register


@register()
def instance_configured(app_configs, **kwargs):
    if settings.INSTANCE_CONFIGURED:
        return []
    return [Warning(
        f"No site configuration found in {settings.INSTANCE_DIR}.",
        hint="Choose the site with INSTANCE_DIR or a `.instance` file, or create one with "
             "`INSTANCE_DIR=instanceName python manage.py init_instance`.",
        id="core.W001",
    )]

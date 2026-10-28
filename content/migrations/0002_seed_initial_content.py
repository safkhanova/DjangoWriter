"""
Generic initial data: the settings singleton and the «Redaktor» permission group.

Site-specific structure (sections, hero, contact topics...) is not created here: it comes
from the instance seed (`manage.py setup_site`, see instance.example/seed.json).
"""

from django.db import migrations


def seed(apps, schema_editor):
    # explicit neutral values: the historical model still carries older site-specific defaults
    apps.get_model("core", "SiteSettings").objects.get_or_create(
        pk=1, defaults={"footer_text": "", "contact_text": "Əməkdaşlıq və suallar üçün yazın."},
    )

    from core.permissions import sync_editor_group

    sync_editor_group(apps)


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0001_initial"),
        ("core", "0001_initial"),
        ("newsletter", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]

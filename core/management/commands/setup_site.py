"""Load the site structure from the instance seed (sections, hero, topics, settings)."""

from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Import instance/seed.json (sections, types, hero, contact topics, social links, site settings)."

    def add_arguments(self, parser):
        parser.add_argument("--seed", default=None, help="Seed file (default: <instance>/seed.json).")
        parser.add_argument("--overwrite", action="store_true", help="Overwrite values already edited in the admin.")

    def handle(self, seed=None, overwrite=False, **options):
        path = seed or settings.INSTANCE_DIR / "seed.json"
        if not Path(path).exists():
            raise CommandError(f"{path} not found. Run `manage.py init_instance` or pass --seed.")
        args = [str(path), "--publish"] + (["--overwrite"] if overwrite else [])
        call_command("import_content", *args, stdout=self.stdout, stderr=self.stderr)

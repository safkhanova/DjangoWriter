"""Create the private instance folder from instance.example/ (first step for a new site)."""

import secrets
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Copy instance.example/ to the instance folder and generate a SECRET_KEY."

    def handle(self, *args, **options):
        source = settings.BASE_DIR / "instance.example"
        target = settings.INSTANCE_DIR
        if (target / ".env").exists():
            raise CommandError(f"{target} already has a .env; nothing was changed.")
        shutil.copytree(source, target, dirs_exist_ok=True)
        env_file = target / ".env"
        shutil.move(target / ".env.example", env_file)
        env_file.write_text(
            env_file.read_text(encoding="utf-8").replace("SECRET_KEY=change-me", f"SECRET_KEY={secrets.token_urlsafe(50)}"),
            encoding="utf-8",
        )
        env_file.chmod(0o600)
        (target / "media").mkdir(exist_ok=True)
        self.stdout.write(self.style.SUCCESS(f"Created {target}."))
        self.stdout.write("Next: edit .env and seed.json there, then run migrate and setup_site.")
        if target.parent == settings.BASE_DIR and target.name != "instance":
            self.stdout.write(f"Select it with `echo {target.name} > .instance` or INSTANCE_DIR={target.name}.")

import getpass

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

from core.permissions import EDITOR_GROUP


class Command(BaseCommand):
    help = "Create (or update) a non-superuser editor account in the «Redaktor» group."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--name", default="")

    def handle(self, email, name, **options):
        email = email.strip().lower()
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError("Invalid e-mail address.") from exc
        password = getpass.getpass("Password: ")
        if not password or password != getpass.getpass("Password (again): "):
            raise CommandError("Passwords are empty or do not match.")

        # username == e-mail: emailotp looks staff up by username.
        user, created = User.objects.get_or_create(username=email, defaults={"email": email})
        user.email, user.first_name, user.is_staff, user.is_active = email, name or user.first_name, True, True
        user.set_password(password)
        user.save()
        user.groups.add(Group.objects.get(name=EDITOR_GROUP))
        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} editor {email}."))

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError

from core.models import UserSession
from core.sessions import revoke_user_sessions


class Command(BaseCommand):
    help = (
        "Emergency logout. `revoke_sessions <email> [...]` logs those users out of every device; "
        "`revoke_sessions --all` logs out everyone. Use with a password change if an account is compromised."
    )

    def add_arguments(self, parser):
        parser.add_argument("emails", nargs="*")
        parser.add_argument("--all", action="store_true", help="Delete every session (all users).")

    def handle(self, emails, all, **options):
        if all:
            count = Session.objects.count()
            Session.objects.all().delete()
            UserSession.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted all {count} sessions."))
            return
        if not emails:
            raise CommandError("Pass one or more e-mail addresses, or --all.")
        for email in emails:
            user = User.objects.filter(username=email.strip().lower()).first()
            if user is None:
                self.stderr.write(f"No user {email}")
                continue
            self.stdout.write(f"{email}: {revoke_user_sessions(user)} session(s) revoked.")

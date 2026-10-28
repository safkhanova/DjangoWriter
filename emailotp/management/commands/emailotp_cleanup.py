"""
Prune expired OTPs and old audit rows.

Run from cron, e.g. nightly:
    0 4 * * * cd /path/to/project && venv/bin/python manage.py emailotp_cleanup

Both tables grow without bound otherwise: EmailOTP gains a row per code sent,
AuthEvent a row per auth action.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from emailotp import conf
from emailotp.models import AuthEvent, EmailOTP


class Command(BaseCommand):
    help = 'Delete expired one-time codes and audit rows past their retention.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--audit-days', type=int, default=conf.AUDIT_RETENTION_DAYS,
            help='Keep AuthEvent rows for this many days (default: %(default)s).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would be deleted without deleting it.',
        )

    def handle(self, *args, **options):
        now = timezone.now()
        audit_cutoff = now - timedelta(days=options['audit_days'])

        # Codes are useless once expired; keep a short grace window so a
        # just-expired code still reports "expired" rather than vanishing.
        otp_cutoff = now - timedelta(hours=24)
        otps = EmailOTP.objects.filter(expires_at__lt=otp_cutoff)
        events = AuthEvent.objects.filter(created_at__lt=audit_cutoff)

        otp_count = otps.count()
        event_count = events.count()

        if options['dry_run']:
            self.stdout.write(
                f'Would delete {otp_count} OTP row(s) and '
                f'{event_count} audit row(s).'
            )
            return

        otps.delete()
        events.delete()
        self.stdout.write(self.style.SUCCESS(
            f'Deleted {otp_count} OTP row(s) and {event_count} audit row(s).'
        ))

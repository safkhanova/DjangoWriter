from django.core.management.base import BaseCommand

from newsletter.services import send_queued


class Command(BaseCommand):
    help = "Send pending e-mails from the queue (run from cron every minute)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Max e-mails in this run.")

    def handle(self, *args, limit=None, **options):
        sent, failed = send_queued(limit)
        if sent or failed:
            self.stdout.write(f"sent={sent} failed={failed}")

from django.core.management.base import BaseCommand

from reports.sending import send_due_reports


class Command(BaseCommand):
    help = "Sends the periodic reports that are due (run once a day)."

    def handle(self, *args, **options):
        self.stdout.write(f"Reports sent: {send_due_reports()}")

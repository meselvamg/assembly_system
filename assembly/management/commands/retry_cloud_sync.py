from django.core.management.base import BaseCommand

from assembly.cloud import build_payload, send_to_cloud
from assembly.models import CloudData


class Command(BaseCommand):
    help = "Resend CloudData entries that are still PENDING or FAILED."

    def handle(self, **options):
        entries = CloudData.objects.filter(sync_status__in=["PENDING", "FAILED"]).order_by("id")
        sent = 0
        for entry in entries:
            entry.sync_status = send_to_cloud(build_payload(entry))
            entry.save(update_fields=["sync_status"])
            sent += entry.sync_status == "SENT"
        self.stdout.write(f"{sent}/{len(entries)} entries sent to cloud")

import json
import logging
import time
from urllib import request as urlrequest

from django.conf import settings

from .models import AssemblyLog, QALog, SCADALog

logger = logging.getLogger(__name__)

# EntryType -> (log model, fields sent to the cloud)
ENTRY_SOURCES = {
    "ASSEMBLY": (AssemblyLog, ["id", "component_id", "assembly_time"]),
    "QA": (QALog, ["id", "component_id", "verification_status", "verification_time"]),
    "SCADA": (SCADALog, ["id", "assembly_status", "scada_time"]),
}


def build_payload(entry):
    model, fields = ENTRY_SOURCES[entry.entry_type]
    records = list(model.objects.filter(mobile_base_id=entry.mobile_base_id).values(*fields))
    return {
        "EntryID": entry.id,
        "MobileBaseID": entry.mobile_base_id,
        "EntryType": entry.entry_type,
        "EntryTime": entry.entry_time,
        "Records": records,
    }


def send_to_cloud(payload):
    """POST payload to CLOUD_API_URL with retries. Returns a CloudData sync_status value."""
    url = settings.CLOUD_API_URL
    if not url:
        logger.warning("CLOUD_API_URL not set, entry %s kept as PENDING", payload["EntryID"])
        return "PENDING"

    body = json.dumps(payload, default=str).encode()
    max_retries = settings.CLOUD_MAX_RETRIES
    for attempt in range(1, max_retries + 1):
        try:
            req = urlrequest.Request(
                url, data=body, headers={"Content-Type": "application/json"}, method="POST"
            )
            with urlrequest.urlopen(req, timeout=settings.CLOUD_TIMEOUT):
                logger.info("Entry %s sent to cloud (attempt %s)", payload["EntryID"], attempt)
                return "SENT"
        except OSError as exc:  # URLError, HTTPError, timeouts, connection resets
            logger.warning(
                "Cloud push for entry %s failed (attempt %s/%s): %s",
                payload["EntryID"], attempt, max_retries, exc,
            )
        if attempt < max_retries:
            time.sleep(settings.CLOUD_RETRY_DELAY * attempt)

    logger.error("Entry %s could not be sent to cloud after %s attempts", payload["EntryID"], max_retries)
    return "FAILED"

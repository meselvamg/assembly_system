import logging

from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Count
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .cloud import ENTRY_SOURCES, build_payload, send_to_cloud
from .models import AssemblyLog, CloudData, MacMini, MobileBase, QALog, SCADALog
from .permissions import role_required
from .serializers import (
    AssemblyLogSerializer,
    CloudReportSerializer,
    LoginSerializer,
    MacMiniSerializer,
    QALogSerializer,
    SCADALogSerializer,
)

logger = logging.getLogger(__name__)


def failure(errors, code=status.HTTP_400_BAD_REQUEST):
    return Response({"status": "Failure", "errors": errors}, status=code)


@api_view(["POST"])
@permission_classes([role_required("OPERATOR", "SUPERVISOR")])
def assemble_component(request):
    serializer = AssemblyLogSerializer(data=request.data)

    if not serializer.is_valid():
        logger.warning("assemble_component rejected: %s", serializer.errors)
        return failure(serializer.errors)

    with transaction.atomic():
        log = serializer.save()
        MobileBase.objects.get_or_create(mobile_base_id=log.mobile_base_id)

    logger.info("Component %s assembled on %s by %s", log.component_id, log.mobile_base_id, request.user)
    return Response(
        {"status": "Success", "message": "Component assembled", "log_id": log.id},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([role_required("TECHNICIAN", "ENGINEER", "SUPERVISOR")])
def verify_component(request):
    serializer = QALogSerializer(data=request.data)

    if not serializer.is_valid():
        logger.warning("verify_component rejected: %s", serializer.errors)
        return failure(serializer.errors)

    log = serializer.save()
    logger.info(
        "QA %s for %s on %s by %s",
        log.verification_status, log.component_id, log.mobile_base_id, request.user,
    )
    return Response(
        {"status": "Success", "message": "Verification saved", "log_id": log.id},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([role_required("ENGINEER", "TECHNICIAN", "SUPERVISOR")])
def scada_integration(request):
    serializer = SCADALogSerializer(data=request.data)

    if not serializer.is_valid():
        logger.warning("scada_integration rejected: %s", serializer.errors)
        return failure(serializer.errors)

    with transaction.atomic():
        log = serializer.save()
        MobileBase.objects.update_or_create(
            mobile_base_id=log.mobile_base_id,
            defaults={"current_status": log.assembly_status},
        )

    logger.info("SCADA status %s for %s", log.assembly_status, log.mobile_base_id)
    return Response(
        {"status": "Success", "message": "SCADA status saved", "log_id": log.id},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([role_required("SUPERVISOR", "ENGINEER")])
def report_to_cloud(request):
    serializer = CloudReportSerializer(data=request.data)

    if not serializer.is_valid():
        logger.warning("report_to_cloud rejected: %s", serializer.errors)
        return failure(serializer.errors)

    base_id = serializer.validated_data["mobile_base_id"]
    entry_type = serializer.validated_data["entry_type"]
    model, _ = ENTRY_SOURCES[entry_type]
    if not model.objects.filter(mobile_base_id=base_id).exists():
        return failure({"MobileBaseID": [f"No {entry_type} records for {base_id}"]})

    entry = serializer.save()
    entry.sync_status = send_to_cloud(build_payload(entry))
    entry.save(update_fields=["sync_status"])

    if entry.sync_status == "FAILED":
        return Response(
            {"status": "Failure", "message": "Saved locally, cloud push failed", "entry_id": entry.id,
             "sync_status": entry.sync_status},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    return Response(
        {"status": "Success", "message": "Reported to cloud", "entry_id": entry.id,
         "sync_status": entry.sync_status},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([role_required("ENGINEER", "SUPERVISOR")])
def integrate_with_cloud(request):
    serializer = MacMiniSerializer(data=request.data)

    if not serializer.is_valid():
        logger.warning("integrate_with_cloud rejected: %s", serializer.errors)
        return failure(serializer.errors)

    mac_mini, created = MacMini.objects.update_or_create(
        mac_mini_id=serializer.validated_data["mac_mini_id"],
        defaults={
            "assembly_area_id": serializer.validated_data["assembly_area_id"],
            "cloud_integration_status": "INTEGRATED",
        },
    )

    logger.info(
        "Mac mini %s %s for area %s",
        mac_mini.mac_mini_id, "registered" if created else "re-integrated", mac_mini.assembly_area_id,
    )
    return Response(
        {"status": "Success", "message": "Mac mini integrated with cloud",
         "mac_mini_id": mac_mini.mac_mini_id, "assembly_area_id": mac_mini.assembly_area_id},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def authorize_user(request):
    serializer = LoginSerializer(data=request.data)

    if not serializer.is_valid():
        return failure(serializer.errors)

    username = serializer.validated_data["Username"]
    user = authenticate(username=username, password=serializer.validated_data["Password"])
    if user is None:
        logger.warning("Failed login for %s", username)
        return Response(
            {"status": "Failure", "message": "Invalid username or password"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token, _ = Token.objects.get_or_create(user=user)
    profile = getattr(user, "profile", None)
    logger.info("User %s logged in", username)
    return Response({
        "status": "Success",
        "token": token.key,
        "user_type": profile.user_type if profile else None,
    })


def count_by(queryset, field, choices):
    counts = {value: 0 for value, _ in choices}
    for row in queryset.values(field).annotate(total=Count("id")):
        counts[row[field] or "UNKNOWN"] = row["total"]
    return counts


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_data(request):
    assembled = dict(AssemblyLog.objects.values_list("mobile_base_id").annotate(Count("id")))
    qa = {}
    for row in QALog.objects.values("mobile_base_id", "verification_status").annotate(total=Count("id")):
        qa.setdefault(row["mobile_base_id"], {"PASS": 0, "FAIL": 0})[row["verification_status"]] = row["total"]

    bases = [
        {
            "MobileBaseID": base.mobile_base_id,
            "current_status": base.current_status or "UNKNOWN",
            "components_assembled": assembled.get(base.mobile_base_id, 0),
            "qa": qa.get(base.mobile_base_id, {"PASS": 0, "FAIL": 0}),
            "updated_at": base.updated_at,
        }
        for base in MobileBase.objects.order_by("-updated_at")[:50]
    ]

    return Response({
        "status": "Success",
        "summary": {
            "mobile_bases": MobileBase.objects.count(),
            "status": count_by(MobileBase.objects, "current_status", SCADALog.STATUS_CHOICES),
            "components_assembled": AssemblyLog.objects.count(),
            "qa": count_by(QALog.objects, "verification_status", QALog.VERIFICATION_CHOICES),
            "cloud_sync": count_by(CloudData.objects, "sync_status", CloudData.SYNC_CHOICES),
            "mac_minis": count_by(MacMini.objects, "cloud_integration_status", MacMini.INTEGRATION_CHOICES),
        },
        "assembly_areas": [
            {
                "AssemblyAreaID": mac_mini.assembly_area_id,
                "MacMiniID": mac_mini.mac_mini_id,
                "cloud_integration_status": mac_mini.cloud_integration_status,
                "last_sync_time": mac_mini.last_sync_time,
            }
            for mac_mini in MacMini.objects.order_by("assembly_area_id")
        ],
        "mobile_bases": bases,
    })

from rest_framework import serializers
from .models import AssemblyLog, QALog


class AssemblyLogSerializer(serializers.ModelSerializer):
    MobileBaseID = serializers.CharField(source="mobile_base_id", max_length=50)
    ComponentID = serializers.CharField(source="component_id", max_length=50)

    class Meta:
        model = AssemblyLog
        fields = ["id", "MobileBaseID", "ComponentID", "assembly_time"]
        read_only_fields = ["id", "assembly_time"]

class QALogSerializer(serializers.ModelSerializer):
    MobileBaseID = serializers.CharField(source="mobile_base_id", max_length=50)
    ComponentID = serializers.CharField(source="component_id", max_length=50)
    VerificationStatus = serializers.ChoiceField(
        source="verification_status",
        choices=QALog.VERIFICATION_CHOICES,
    )

    class Meta:
        model = QALog
        fields = ["id", "MobileBaseID", "ComponentID", "VerificationStatus", "verification_time"]
        read_only_fields = ["id", "verification_time"]



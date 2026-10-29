from rest_framework import serializers
from .models import AssemblyLog, CloudData, QALog, SCADALog



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




class SCADALogSerializer(serializers.ModelSerializer):
    MobileBaseID = serializers.CharField(source="mobile_base_id", max_length=50)
    AssemblyStatus = serializers.ChoiceField(
        source="assembly_status",
        choices=SCADALog.STATUS_CHOICES,
    )

    class Meta:
        model = SCADALog
        fields = ["id", "MobileBaseID", "AssemblyStatus", "scada_time"]
        read_only_fields = ["id", "scada_time"]


class CloudReportSerializer(serializers.ModelSerializer):
    MobileBaseID = serializers.CharField(source="mobile_base_id", max_length=50)
    EntryType = serializers.ChoiceField(
        source="entry_type",
        choices=CloudData.ENTRY_TYPE_CHOICES,
    )

    class Meta:
        model = CloudData
        fields = ["id", "MobileBaseID", "EntryType", "entry_time", "sync_status"]
        read_only_fields = ["id", "entry_time", "sync_status"]


class LoginSerializer(serializers.Serializer):
    Username = serializers.CharField(max_length=150)
    Password = serializers.CharField(write_only=True, trim_whitespace=False)

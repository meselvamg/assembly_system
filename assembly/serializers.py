from rest_framework import serializers
from .models import AssemblyLog


class AssemblyLogSerializer(serializers.ModelSerializer):
    MobileBaseID = serializers.CharField(source="mobile_base_id", max_length=50)
    ComponentID = serializers.CharField(source="component_id", max_length=50)

    class Meta:
        model = AssemblyLog
        fields = ["id", "MobileBaseID", "ComponentID", "assembly_time"]
        read_only_fields = ["id", "assembly_time"]
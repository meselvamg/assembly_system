from django.contrib import admin

from .models import AssemblyLog, CloudData, MacMini, MobileBase, QALog, SCADALog, UserProfile


@admin.register(MobileBase)
class MobileBaseAdmin(admin.ModelAdmin):
    list_display = ["mobile_base_id", "current_status", "updated_at"]
    list_filter = ["current_status"]


@admin.register(AssemblyLog)
class AssemblyLogAdmin(admin.ModelAdmin):
    list_display = ["id", "mobile_base_id", "component_id", "assembly_time"]
    search_fields = ["mobile_base_id", "component_id"]


@admin.register(QALog)
class QALogAdmin(admin.ModelAdmin):
    list_display = ["id", "mobile_base_id", "component_id", "verification_status", "verification_time"]
    list_filter = ["verification_status"]


@admin.register(SCADALog)
class SCADALogAdmin(admin.ModelAdmin):
    list_display = ["id", "mobile_base_id", "assembly_status", "scada_time"]
    list_filter = ["assembly_status"]


@admin.register(CloudData)
class CloudDataAdmin(admin.ModelAdmin):
    list_display = ["id", "mobile_base_id", "entry_type", "sync_status", "entry_time"]
    list_filter = ["entry_type", "sync_status"]


@admin.register(MacMini)
class MacMiniAdmin(admin.ModelAdmin):
    list_display = ["mac_mini_id", "assembly_area_id", "cloud_integration_status", "last_sync_time"]
    list_filter = ["assembly_area_id", "cloud_integration_status"]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "user_type"]
    list_filter = ["user_type"]

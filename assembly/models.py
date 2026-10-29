from django.conf import settings
from django.db import models

class AssemblyLog(models.Model):
    mobile_base_id = models.CharField(max_length=50)
    component_id = models.CharField(max_length=50)
    assembly_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.mobile_base_id} - {self.component_id}"   


class QALog(models.Model):
    VERIFICATION_CHOICES = [
        ('PASS', 'Pass'),
        ('FAIL', 'Fail'),      
    ]

    mobile_base_id = models.CharField(max_length=50)
    component_id = models.CharField(max_length=50)
    verification_status = models.CharField(max_length=4, choices=VERIFICATION_CHOICES)
    verification_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.mobile_base_id} - {self.component_id} - {self.verification_status}"


class SCADALog(models.Model):
    STATUS_CHOICES = [
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('ERROR', 'Error'),
    ]

    mobile_base_id = models.CharField(max_length=50)
    assembly_status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    scada_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.mobile_base_id} - {self.assembly_status}"


class MobileBase(models.Model):
    mobile_base_id = models.CharField(max_length=50, unique=True)
    current_status = models.CharField(
        max_length=10, choices=SCADALog.STATUS_CHOICES, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.mobile_base_id


class CloudData(models.Model):
    ENTRY_TYPE_CHOICES = [
        ('ASSEMBLY', 'Assembly'),
        ('QA', 'QA'),
        ('SCADA', 'SCADA'),
    ]
    SYNC_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
    ]

    mobile_base_id = models.CharField(max_length=50)
    entry_type = models.CharField(max_length=8, choices=ENTRY_TYPE_CHOICES)
    entry_time = models.DateTimeField(auto_now_add=True)
    sync_status = models.CharField(max_length=7, choices=SYNC_CHOICES, default='PENDING')

    def __str__(self):
        return f"{self.mobile_base_id} - {self.entry_type} - {self.sync_status}"


class UserProfile(models.Model):
    USER_TYPE_CHOICES = [
        ('SUPERVISOR', 'Supervisor'),
        ('OPERATOR', 'Manual Operator'),
        ('TECHNICIAN', 'Technician'),
        ('ENGINEER', 'Engineer'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)

    def __str__(self):
        return f"{self.user.username} - {self.user_type}"

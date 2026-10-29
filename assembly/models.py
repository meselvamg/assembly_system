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
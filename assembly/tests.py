from django.test import TestCase
from rest_framework.test import APIClient
from .models import AssemblyLog


class AssembleComponentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/assemble_component/"

    def test_valid_data_creates_log(self):
        response = self.client.post(
            self.url,
            {"MobileBaseID": "MB001", "ComponentID": "CMP100"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "Success")
        self.assertEqual(AssemblyLog.objects.count(), 1)

    def test_missing_component_returns_400(self):
        response = self.client.post(
            self.url,
            {"MobileBaseID": "MB001"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "Failure")
        self.assertEqual(AssemblyLog.objects.count(), 0)
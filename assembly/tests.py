from unittest.mock import patch
from urllib.error import URLError

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .cloud import send_to_cloud
from .models import AssemblyLog, CloudData, MobileBase, QALog, SCADALog, UserProfile


def make_user(username, user_type, password="pass1234"):
    user = User.objects.create_user(username=username, password=password)
    UserProfile.objects.create(user=user, user_type=user_type)
    return user


class AssembleComponentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(make_user("operator", "OPERATOR"))
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
        self.assertTrue(MobileBase.objects.filter(mobile_base_id="MB001").exists())

    def test_missing_component_returns_400(self):
        response = self.client.post(
            self.url,
            {"MobileBaseID": "MB001"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "Failure")
        self.assertEqual(AssemblyLog.objects.count(), 0)


class VerifyComponentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(make_user("tech", "TECHNICIAN"))
        self.url = "/api/verify_component/"

    def test_valid_verification_creates_log(self):
        response = self.client.post(
            self.url,
            {"MobileBaseID": "MB001", "ComponentID": "CMP100", "VerificationStatus": "PASS"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "Success")
        self.assertEqual(QALog.objects.count(), 1)

    def test_invalid_status_returns_400(self):
        response = self.client.post(
            self.url,
            {"MobileBaseID": "MB001", "ComponentID": "CMP100", "VerificationStatus": "MAYBE"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "Failure")
        self.assertEqual(QALog.objects.count(), 0)


class SCADAIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(make_user("engineer", "ENGINEER"))
        self.url = "/api/scada_integration/"

    def test_valid_status_creates_log(self):
        response = self.client.post(
            self.url,
            {"MobileBaseID": "MB001", "AssemblyStatus": "RUNNING"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "Success")
        self.assertEqual(SCADALog.objects.count(), 1)

    def test_status_updates_mobile_base(self):
        for status in ["RUNNING", "COMPLETED"]:
            self.client.post(self.url, {"MobileBaseID": "MB001", "AssemblyStatus": status}, format="json")
        self.assertEqual(MobileBase.objects.get(mobile_base_id="MB001").current_status, "COMPLETED")

    def test_invalid_status_returns_400(self):
        response = self.client.post(
            self.url,
            {"MobileBaseID": "MB001", "AssemblyStatus": "BROKEN"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "Failure")
        self.assertEqual(SCADALog.objects.count(), 0)

    def test_missing_mobile_base_returns_400(self):
        response = self.client.post(
            self.url,
            {"AssemblyStatus": "RUNNING"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "Failure")
        self.assertEqual(SCADALog.objects.count(), 0)


class ReportToCloudTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(make_user("supervisor", "SUPERVISOR"))
        self.url = "/api/report_to_cloud/"
        AssemblyLog.objects.create(mobile_base_id="MB001", component_id="CMP100")

    def test_without_cloud_url_entry_stays_pending(self):
        response = self.client.post(self.url, {"MobileBaseID": "MB001", "EntryType": "ASSEMBLY"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["sync_status"], "PENDING")
        self.assertIn("waiting for cloud", response.data["message"])
        self.assertEqual(CloudData.objects.get().sync_status, "PENDING")

    @patch("assembly.views.send_to_cloud", return_value="SENT")
    def test_successful_push_marks_sent(self, mock_send):
        response = self.client.post(self.url, {"MobileBaseID": "MB001", "EntryType": "ASSEMBLY"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(CloudData.objects.get().sync_status, "SENT")
        payload = mock_send.call_args.args[0]
        self.assertEqual(payload["Records"][0]["component_id"], "CMP100")

    @patch("assembly.views.send_to_cloud", return_value="FAILED")
    def test_failed_push_returns_failure(self, mock_send):
        response = self.client.post(self.url, {"MobileBaseID": "MB001", "EntryType": "ASSEMBLY"}, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["status"], "Failure")
        self.assertEqual(CloudData.objects.get().sync_status, "FAILED")

    def test_no_records_returns_400(self):
        response = self.client.post(self.url, {"MobileBaseID": "MB001", "EntryType": "QA"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(CloudData.objects.count(), 0)

    def test_invalid_entry_type_returns_400(self):
        response = self.client.post(self.url, {"MobileBaseID": "MB001", "EntryType": "OTHER"}, format="json")
        self.assertEqual(response.status_code, 400)


@override_settings(CLOUD_API_URL="http://cloud.invalid/ingest", CLOUD_MAX_RETRIES=3, CLOUD_RETRY_DELAY=0)
class SendToCloudRetryTests(TestCase):
    payload = {"EntryID": 1, "MobileBaseID": "MB001", "EntryType": "QA", "Records": []}

    @patch("assembly.cloud.urlrequest.urlopen", side_effect=URLError("down"))
    def test_retries_then_fails(self, mock_urlopen):
        self.assertEqual(send_to_cloud(self.payload), "FAILED")
        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("assembly.cloud.urlrequest.urlopen")
    def test_succeeds_after_retry(self, mock_urlopen):
        mock_urlopen.side_effect = [URLError("down"), mock_urlopen.return_value]
        self.assertEqual(send_to_cloud(self.payload), "SENT")
        self.assertEqual(mock_urlopen.call_count, 2)


class AuthorizationTests(TestCase):
    def setUp(self):
        cache.clear()  # reset the login throttle between tests
        self.client = APIClient()
        make_user("operator", "OPERATOR")

    def test_login_returns_token_and_role(self):
        response = self.client.post(
            "/api/authorize_user/", {"Username": "operator", "Password": "pass1234"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user_type"], "OPERATOR")
        self.assertTrue(response.data["token"])

    def test_login_is_rate_limited(self):
        for _ in range(5):
            self.client.post("/api/authorize_user/", {"Username": "operator", "Password": "wrong"}, format="json")
        response = self.client.post(
            "/api/authorize_user/", {"Username": "operator", "Password": "pass1234"}, format="json"
        )
        self.assertEqual(response.status_code, 429)

    def test_wrong_password_returns_401(self):
        response = self.client.post(
            "/api/authorize_user/", {"Username": "operator", "Password": "wrong"}, format="json"
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["status"], "Failure")

    def test_token_allows_api_call(self):
        token = self.client.post(
            "/api/authorize_user/", {"Username": "operator", "Password": "pass1234"}, format="json"
        ).data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        response = self.client.post(
            "/api/assemble_component/", {"MobileBaseID": "MB001", "ComponentID": "CMP100"}, format="json"
        )
        self.assertEqual(response.status_code, 201)

    def test_no_token_returns_401(self):
        response = self.client.post(
            "/api/assemble_component/", {"MobileBaseID": "MB001", "ComponentID": "CMP100"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_wrong_role_returns_403(self):
        self.client.force_authenticate(User.objects.get(username="operator"))
        response = self.client.post(
            "/api/verify_component/",
            {"MobileBaseID": "MB001", "ComponentID": "CMP100", "VerificationStatus": "PASS"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(QALog.objects.count(), 0)


class DashboardDataTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(make_user("operator", "OPERATOR"))
        MobileBase.objects.create(mobile_base_id="MB001", current_status="RUNNING")
        AssemblyLog.objects.create(mobile_base_id="MB001", component_id="CMP100")
        AssemblyLog.objects.create(mobile_base_id="MB001", component_id="CMP101")
        QALog.objects.create(mobile_base_id="MB001", component_id="CMP100", verification_status="PASS")
        QALog.objects.create(mobile_base_id="MB001", component_id="CMP101", verification_status="FAIL")

    def test_dashboard_summary(self):
        response = self.client.get("/api/dashboard_data/")
        self.assertEqual(response.status_code, 200)
        summary = response.data["summary"]
        self.assertEqual(summary["mobile_bases"], 1)
        self.assertEqual(summary["status"]["RUNNING"], 1)
        self.assertEqual(summary["components_assembled"], 2)
        self.assertEqual(summary["qa"], {"PASS": 1, "FAIL": 1})

        base = response.data["mobile_bases"][0]
        self.assertEqual(base["MobileBaseID"], "MB001")
        self.assertEqual(base["components_assembled"], 2)
        self.assertEqual(base["qa"], {"PASS": 1, "FAIL": 1})

    def test_dashboard_requires_login(self):
        self.assertEqual(APIClient().get("/api/dashboard_data/").status_code, 401)


class DashboardPageTests(TestCase):
    def test_redirects_to_login_when_signed_out(self):
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/accounts/login/"))

    def test_login_then_dashboard_and_data(self):
        make_user("sup", "SUPERVISOR")
        response = self.client.post("/accounts/login/", {"username": "sup", "password": "pass1234"})
        self.assertRedirects(response, "/dashboard/")

        page = self.client.get("/dashboard/")
        self.assertContains(page, "Mobile Manufacturing Assembly &amp; QA Platform")
        self.assertContains(page, "Supervisor")

        # the page's JavaScript reads the API with the same session cookie
        self.assertEqual(self.client.get("/api/dashboard_data/").status_code, 200)

    def test_wrong_password_shows_error(self):
        make_user("sup", "SUPERVISOR")
        response = self.client.post("/accounts/login/", {"username": "sup", "password": "wrong"})
        self.assertContains(response, "Invalid username or password.")


@override_settings(CORS_ALLOWED_ORIGINS=["http://127.0.0.1:5500"])
class FrontendCorsTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_preflight_from_frontend_is_allowed(self):
        response = self.client.options(
            "/api/assemble_component/",
            headers={"Origin": "http://127.0.0.1:5500", "Access-Control-Request-Method": "POST"},
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://127.0.0.1:5500")
        self.assertIn("Authorization", response["Access-Control-Allow-Headers"])

    def test_api_response_carries_cors_header(self):
        make_user("operator", "OPERATOR")
        response = self.client.post(
            "/api/authorize_user/",
            {"Username": "operator", "Password": "pass1234"},
            content_type="application/json",
            headers={"Origin": "http://127.0.0.1:5500"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://127.0.0.1:5500")

    def test_other_origin_gets_no_cors_header(self):
        response = self.client.options(
            "/api/assemble_component/",
            headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
        )
        self.assertNotIn("Access-Control-Allow-Origin", response)

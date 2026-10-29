# Mobile Manufacturing Assembly & QA Platform

> PRJ21.2 (Mobile Assembly System) of the PRJ21 mobile manufacturing spec.

Backend for a mobile phone assembly line. It records every step a phone goes through (component assembly, QA verification, SCADA line status), reports that data to a central cloud with retries, and exposes a monitoring dashboard API. Access is controlled with token authentication and four user roles.

Built with **Django 6.1** and **Django REST Framework 3.18**.

## How a phone moves through the system

```
Operator      POST /api/assemble_component/   MB001 + CAM-01 fitted     -> AssemblyLog
Technician    POST /api/verify_component/     CAM-01 on MB001 = PASS    -> QALog
SCADA         POST /api/scada_integration/    MB001 = COMPLETED         -> SCADALog + MobileBase status
Supervisor    POST /api/report_to_cloud/      send MB001 QA data        -> CloudData + HTTP push to cloud
Anyone        GET  /api/dashboard_data/       live summary of the line
```

Every request (except login) needs a token from `/api/authorize_user/`.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py create_factory_user op1 Op@12345 OPERATOR
python manage.py runserver
```

## Configuration

All settings have safe local defaults; production values come from environment variables.

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_DEBUG` | `1` | Set to `0` in production (also turns on HTTPS redirect and secure cookies) |
| `DJANGO_SECRET_KEY` | dev-only key | **Required** when `DJANGO_DEBUG=0`; the app refuses to start without it |
| `DJANGO_ALLOWED_HOSTS` | empty | Comma-separated hostnames, e.g. `myapp.onrender.com` |
| `CLOUD_API_URL` | empty | Cloud endpoint for `report_to_cloud`. Empty means entries are stored as `PENDING` and not sent |

Generate a secret key with:
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

## Roles

| API | Operator | Technician | Engineer | Supervisor |
|---|:-:|:-:|:-:|:-:|
| `assemble_component` | ✅ | | | ✅ |
| `verify_component` | | ✅ | ✅ | ✅ |
| `scada_integration` | | ✅ | ✅ | ✅ |
| `report_to_cloud` | | | ✅ | ✅ |
| `dashboard_data` | ✅ | ✅ | ✅ | ✅ |

Superusers can call every API. Missing or invalid token returns `401`; wrong role returns `403`.

## API reference

All endpoints are under `/api/`, accept and return JSON, and respond with `{"status": "Success" | "Failure", ...}`.

### `POST /api/authorize_user/`
```json
{"Username": "op1", "Password": "Op@12345"}
```
`200` → `{"status": "Success", "token": "9f2c...", "user_type": "OPERATOR"}`
`401` → invalid username or password

Send the token on every other request:
```
Authorization: Token 9f2c...
```

### `POST /api/assemble_component/`
```json
{"MobileBaseID": "MB001", "ComponentID": "CAM-01"}
```
`201` → `{"status": "Success", "message": "Component assembled", "log_id": 1}`. Also registers the mobile base if it is new.

### `POST /api/verify_component/`
```json
{"MobileBaseID": "MB001", "ComponentID": "CAM-01", "VerificationStatus": "PASS"}
```
`VerificationStatus` is `PASS` or `FAIL`. `201` → `{"status": "Success", "message": "Verification saved", "log_id": 1}`

### `POST /api/scada_integration/`
```json
{"MobileBaseID": "MB001", "AssemblyStatus": "COMPLETED"}
```
`AssemblyStatus` is `RUNNING`, `COMPLETED` or `ERROR`. Updates the mobile base's current status.
`201` → `{"status": "Success", "message": "SCADA status saved", "log_id": 1}`

### `POST /api/report_to_cloud/`
```json
{"MobileBaseID": "MB001", "EntryType": "QA"}
```
`EntryType` is `ASSEMBLY`, `QA` or `SCADA`. Collects all records of that type for the mobile base and POSTs them to `CLOUD_API_URL`, retrying up to 3 times with backoff.

| Result | Response |
|---|---|
| Sent | `201`, `sync_status: "SENT"` |
| No `CLOUD_API_URL` configured | `201`, `sync_status: "PENDING"` |
| Cloud unreachable after retries | `502`, `sync_status: "FAILED"` (entry kept for retry) |
| No records of that type for the base | `400` |

Payload sent to the cloud:
```json
{
  "EntryID": 1, "MobileBaseID": "MB001", "EntryType": "QA", "EntryTime": "...",
  "Records": [{"id": 1, "component_id": "CAM-01", "verification_status": "PASS", "verification_time": "..."}]
}
```

### `GET /api/dashboard_data/`
```json
{
  "status": "Success",
  "summary": {
    "mobile_bases": 1,
    "status": {"RUNNING": 0, "COMPLETED": 1, "ERROR": 0},
    "components_assembled": 1,
    "qa": {"PASS": 1, "FAIL": 0},
    "cloud_sync": {"PENDING": 0, "SENT": 1, "FAILED": 0}
  },
  "mobile_bases": [
    {"MobileBaseID": "MB001", "current_status": "COMPLETED", "components_assembled": 1,
     "qa": {"PASS": 1, "FAIL": 0}, "updated_at": "..."}
  ]
}
```

## Monitoring dashboard

Open `http://127.0.0.1:8000/` and sign in with any factory account. The page shows mobile bases, components assembled, QA pass rate, cloud backlog, line status / QA / cloud sync breakdowns and a per-base table, refreshing every 10 seconds from `/api/dashboard_data/`. It uses Django session login (`/accounts/login/`), so no token is needed in the browser.

## Database schema

| Table | Columns |
|---|---|
| `MobileBase` | mobile_base_id (unique), current_status, created_at, updated_at |
| `AssemblyLog` | id, mobile_base_id, component_id, assembly_time |
| `QALog` | id, mobile_base_id, component_id, verification_status, verification_time |
| `SCADALog` | id, mobile_base_id, assembly_status, scada_time |
| `CloudData` | id, mobile_base_id, entry_type, entry_time, sync_status |
| `UserProfile` | user (one-to-one with Django user), user_type |

All tables can be browsed at `/admin/` after `python manage.py createsuperuser`.

## Management commands

```bash
# Create a user with a role: SUPERVISOR, OPERATOR, TECHNICIAN or ENGINEER
python manage.py create_factory_user <username> <password> <role>

# Resend every CloudData entry that is still PENDING or FAILED (run from cron in production)
python manage.py retry_cloud_sync
```

## Logging

Events and errors are written to the console and to `logs/assembly.log` (rotated at 5 MB, 3 backups): logins, failed logins, every saved log entry, rejected requests and each cloud push attempt.

## Tests

```bash
python manage.py test assembly
```

25 tests cover every endpoint: valid and invalid input, role checks, token login, cloud push success, failure and retry, the dashboard summary, and the dashboard page login flow.

## Project structure

```
config/
  settings.py        DRF, auth, cloud, logging and security settings
  urls.py            /admin/ and /api/
assembly/
  models.py          Database tables
  serializers.py     Request validation and field mapping (MobileBaseID -> mobile_base_id)
  views.py           API endpoints
  permissions.py     Role-based access (role_required)
  cloud.py           Cloud payload builder and HTTP push with retries
  urls.py            API routes
  admin.py           Admin pages
  tests.py           Test suite
  templates/
    assembly/        Dashboard page and shared base layout
    registration/    Login page
  management/commands/
    create_factory_user.py
    retry_cloud_sync.py
```

## Part of PRJ21

This repository, the **Mobile Manufacturing Assembly & QA Platform**, implements **PRJ21.2: Mobile Assembly System**. PRJ21.1 (Component Manufacturing) and PRJ21.3 (Centralized Cloud) are separate projects.

from django.conf import settings
from django.http import HttpResponse
from django.utils.cache import patch_vary_headers


class ApiCorsMiddleware:
    """Let the separate frontend (another origin) call /api/ with a token header."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin")
        allowed = request.path.startswith("/api/") and origin in settings.CORS_ALLOWED_ORIGINS

        if allowed and request.method == "OPTIONS" and "Access-Control-Request-Method" in request.headers:
            response = HttpResponse(status=204)  # preflight
        else:
            response = self.get_response(request)

        if allowed:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response["Access-Control-Max-Age"] = "600"
            patch_vary_headers(response, ["Origin"])
        return response

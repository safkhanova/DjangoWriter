"""Security headers for the public site (the admin keeps Unfold's own, it relies on inline scripts)."""

from django.conf import settings


def build_csp() -> str:
    extra = " ".join(settings.CSP_EXTRA_SCRIPT_SRC)
    directives = {
        "default-src": "'self'",
        "script-src": f"'self' {extra}".strip(),
        "connect-src": f"'self' {extra}".strip(),
        # inline style attributes carry design tokens and image widths
        "style-src": "'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src": "'self' https://fonts.gstatic.com",
        "img-src": "'self' data: https://i.ytimg.com",
        "media-src": "'self'",
        "frame-src": "https://www.youtube-nocookie.com",
        "object-src": "'none'",
        "base-uri": "'self'",
        "form-action": "'self'",
        "frame-ancestors": "'none'",
    }
    return "; ".join(f"{name} {value}" for name, value in directives.items())


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.csp = build_csp()

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path_info.startswith("/" + settings.ADMIN_URL):
            response.setdefault("Content-Security-Policy", self.csp)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        return response

from django.conf import settings

from content.models import visible_sections

from .models import SiteSettings, SocialLink
from .utils import is_preview_user


def site(request):
    """Globals for every public template: settings, design tokens, navigation, preview flag."""
    if request.path.startswith("/" + settings.ADMIN_URL):
        return {}
    site_settings = SiteSettings.load()
    return {
        "site": site_settings,
        "fonts": site_settings.fonts,
        "colors": site_settings.colors,
        "nav_sections": [s for s in visible_sections(request.user) if s.show_in_nav],
        "social_links": SocialLink.objects.filter(is_visible=True),
        "preview_mode": is_preview_user(request.user),
    }

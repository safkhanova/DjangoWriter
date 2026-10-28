from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import RedirectView

from content.views import ArticleSitemap, SectionSitemap
from core.auth_guard import guarded_login_password
from core.views import robots_txt

# The admin's own password form would bypass the e-mail code (2nd factor):
# send every admin login through the emailotp flow instead.
admin.site.login = staff_member_required(admin.site.login, login_url="emailotp:login")

# The site has no public accounts: registration pages of emailotp are disabled.
no_registration = RedirectView.as_view(pattern_name="emailotp:login", permanent=False)

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("register/", no_registration),
    path("register/verify/", no_registration),
    path("register/resend/", no_registration),
    # Same URL and name as emailotp's view, wrapped with a brute-force limit; must precede the include.
    path("login/password/", guarded_login_password, name="emailotp_login_password_guarded"),
    path("", include("emailotp.urls")),
    path("abune/", include("newsletter.urls")),
    path("sitemap.xml", sitemap, {"sitemaps": {"articles": ArticleSitemap, "sections": SectionSitemap}}, name="sitemap"),
    path("robots.txt", robots_txt),
    path("", include("core.urls")),
    path("", include("content.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

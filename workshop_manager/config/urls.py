from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from workshop_manager.accounts.views import login_link, request_login_code
from workshop_manager.core.views import healthz, static_redirect

admin.site.site_header = "Manager Warsztatów — administracja techniczna"
admin.site.site_title = "Manager Warsztatów"

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    # Browsers and feed readers ask for these at the root, whatever the page's <link> says.
    path("favicon.ico", static_redirect, {"path": "img/favicon.ico"}),
    path("apple-touch-icon.png", static_redirect, {"path": "img/apple-touch-icon.png"}),
    path("django-admin/", admin.site.urls),
    # Sign-in is by code only (ADR-0001): the password login page forwards to the code request.
    path(
        "konto/login/",
        RedirectView.as_view(pattern_name="account_request_login_code", query_string=True),
    ),
    path("konto/login/code/", request_login_code, name="account_request_login_code"),
    path("konto/link/<str:token>/", login_link, name="account_login_link"),
    path("konto/", include("allauth.urls")),
    path("panel/", include("workshop_manager.panel.urls")),
    path("", include("workshop_manager.public.urls")),
]

# Uploaded files in DEV; servers serve MEDIA_ROOT from the reverse proxy (`static()` is a no-op
# when DEBUG is off).
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

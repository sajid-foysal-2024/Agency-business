"""Root URL configuration. Each app keeps its own urls.py and is included here."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("developers/", include("developers.urls")),
    path("services/", include("service.urls")),
    path("contact/", include("contact.urls")),
    path("accounts/", include("accounts.urls")),
    path("payments/", include("payments.urls")),
    path("", include("orders.urls")),
    path("", include("home.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

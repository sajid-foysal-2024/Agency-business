from service.models import Service

from .models import SiteSetting

FOOTER_SERVICES_LIMIT = 5


def site_settings(request):
    """Data every page needs: {{ site }} settings and the footer service list."""
    return {
        "site": SiteSetting.load(),
        "footer_services": Service.objects.active().only("title", "slug")[:FOOTER_SERVICES_LIMIT],
    }

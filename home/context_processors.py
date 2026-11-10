from .models import Service, SiteSetting

FOOTER_SERVICES_LIMIT = 5


def site_settings(request):
    """Data every page needs: {{ site }} settings and the footer service list."""
    return {
        "site": SiteSetting.load(),
        "footer_services": Service.objects.filter(is_active=True).only("title")[:FOOTER_SERVICES_LIMIT],
    }

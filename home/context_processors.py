from .models import SiteSetting


def site_settings(request):
    """Make the global site settings available as {{ site }} in every template."""
    return {"site": SiteSetting.load()}

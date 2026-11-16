"""Read-only database queries for the service app."""
from django.db.models import Min, Prefetch, Q
from django.shortcuts import get_object_or_404

from .models import FAQ, Package, PackageFeature, Service, ServiceCategory

FEATURES_PREFETCH = Prefetch("features", queryset=PackageFeature.objects.all())


def _packages():
    """Active packages with their features and included services loaded."""
    return (Package.objects.active()
            .select_related("service")
            .prefetch_related(FEATURES_PREFETCH,
                              Prefetch("included_services", queryset=Service.objects.active())))


def get_active_services():
    """Active services with their lowest single-package price in each currency."""
    single = Q(packages__is_active=True, packages__package_type=Package.SINGLE)
    return Service.objects.active().select_related("category").annotate(
        from_price_bdt=Min("packages__price_bdt", filter=single),
        from_price_usd=Min("packages__price_usd", filter=single),
    )


def get_service(slug):
    queryset = Service.objects.active().select_related("category").prefetch_related("offerings")
    return get_object_or_404(queryset, slug=slug)


def get_single_packages(service):
    return _packages().single().filter(service=service)


def get_combo_packages(service=None):
    """Combos that include `service` (or every combo when no service is given)."""
    combos = _packages().combo()
    if service is not None:
        combos = combos.filter(included_services=service)
    return combos.distinct()


def get_featured_packages():
    return _packages().filter(is_featured=True).filter(
        Q(package_type=Package.COMBO) | Q(service__is_active=True)
    )


def get_faqs(service):
    """Questions for this service plus the general ones."""
    return FAQ.objects.filter(is_active=True).filter(Q(service=service) | Q(service__isnull=True))


def get_categories_with_services():
    """Active categories that have active services, plus a list of uncategorised services."""
    services = list(get_active_services())
    categories = []
    for category in ServiceCategory.objects.filter(is_active=True):
        items = [s for s in services if s.category_id == category.id]
        if items:
            categories.append({"category": category, "services": items})
    uncategorised = [s for s in services if s.category_id is None or not s.category.is_active]
    return categories, uncategorised

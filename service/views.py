from django.urls import reverse
from django.views.generic import DetailView, TemplateView

from home.models import SiteSetting

from . import selectors
from .models import AddOn
from .whatsapp import attach_whatsapp_links, general_whatsapp_url


def crumb(label, url=None):
    return {"label": label, "url": url}


class ServiceListView(TemplateView):
    """All services (grouped by category) and featured packages."""

    template_name = "service/service_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site = SiteSetting.load()
        categories, uncategorised = selectors.get_categories_with_services()
        services = uncategorised + [s for group in categories for s in group["services"]]
        featured = attach_whatsapp_links(list(selectors.get_featured_packages()), site)
        context.update({
            "categories": categories,
            "uncategorised": uncategorised,
            "featured_packages": featured,
            "has_prices": bool(featured) or any(
                s.from_price_bdt is not None or s.from_price_usd is not None for s in services),
            "whatsapp_url": general_whatsapp_url(site),
            "breadcrumbs": [crumb("Services")],
        })
        return context


class ServiceDetailView(DetailView):
    """One service: hero, overview, offerings, packages, FAQ and WhatsApp CTA."""

    template_name = "service/service_detail.html"
    context_object_name = "service"

    def get_object(self, queryset=None):
        return selectors.get_service(self.kwargs["slug"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service = self.object
        site = SiteSetting.load()
        context.update({
            "single_packages": attach_whatsapp_links(list(selectors.get_single_packages(service)), site, service),
            "combo_packages": attach_whatsapp_links(list(selectors.get_combo_packages(service)), site, service),
            "faqs": selectors.get_faqs(service),
            "addons": AddOn.objects.for_service(service),
            "whatsapp_url": general_whatsapp_url(site, service),
            "breadcrumbs": [crumb("Services", reverse("services:list")), crumb(service.title)],
        })
        return context

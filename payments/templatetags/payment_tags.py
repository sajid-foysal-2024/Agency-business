"""{% accepted_payments %}: "We accept" logos for the payment methods that are really available."""
from django import template

from payments.models import PaymentBrand
from payments.providers import available_methods
from service.models import CURRENCIES

register = template.Library()


def accepted_brands():
    """Active brands of enabled + configured methods, grouped by market."""
    method_ids = {config.pk for currency in CURRENCIES for config, _ in available_methods(currency)}
    brands = PaymentBrand.objects.filter(is_active=True, methods__pk__in=method_ids).distinct()
    groups = {PaymentBrand.INTERNATIONAL: [], PaymentBrand.BANGLADESH: []}
    for brand in brands:
        groups[brand.market].append(brand)
    return groups


@register.inclusion_tag("payments/partials/_accepted.html")
def accepted_payments(variant="footer"):
    groups = accepted_brands()
    return {
        "variant": variant,
        "international": groups[PaymentBrand.INTERNATIONAL],
        "bangladesh": groups[PaymentBrand.BANGLADESH],
    }

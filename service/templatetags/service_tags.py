from django import template

from service.models import format_price

register = template.Library()


@register.filter
def price(value, currency):
    """{{ amount|price:"bdt" }} -> "৳ 15,000" (empty when the amount is missing)."""
    return format_price(value, currency)

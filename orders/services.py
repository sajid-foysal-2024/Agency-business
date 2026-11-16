"""Creating orders. Every price comes from the database, never from the browser."""
from django.db import transaction

from service.models import AddOn, Package

from .models import CustomerProfile, Order, OrderItem


class CheckoutError(Exception):
    pass


def get_profile(user):
    profile, _ = CustomerProfile.objects.get_or_create(user=user)
    return profile


def checkout_addons(package, currency):
    """Add-ons a customer may pick for this package, with a price in this currency."""
    services = [package.service] if package.service_id else list(package.included_services.all())
    addons = AddOn.objects.active().filter(service__isnull=True)
    for service in services:
        addons = addons | AddOn.objects.active().filter(service=service)
    field = f"price_{currency}__isnull"
    return addons.filter(**{field: False}).distinct()


@transaction.atomic
def create_order(user, package, currency, addons, contact):
    """Create a Draft order for one package plus add-ons. `contact` = cleaned form data."""
    package = Package.objects.select_for_update().get(pk=package.pk)
    if not package.can_checkout(currency):
        raise CheckoutError("This package has no online price in this currency. Please request a quote.")
    if package.service_id and not package.service.is_active:
        raise CheckoutError("This service is not available right now.")

    allowed = set(checkout_addons(package, currency).values_list("pk", flat=True))
    if any(addon.pk not in allowed for addon in addons):
        raise CheckoutError("One of the selected add-ons is not available.")

    order = Order.objects.create(
        user=user, currency=currency, status=Order.DRAFT,
        full_name=contact["full_name"], email=contact["email"], phone=contact.get("phone", ""),
        company=contact.get("company", ""), country=contact.get("country", ""), notes=contact.get("notes", ""),
    )
    service_name = package.service.title if package.service_id else "Combo"
    OrderItem.objects.create(
        order=order, kind=OrderItem.PACKAGE, package=package, service_name=service_name,
        name=f"{service_name} - {package.name}" if package.service_id else package.name,
        billing_type=package.billing_type, unit_price=package.price(currency),
        regular_price=getattr(package, f"regular_price_{currency}"),
    )
    for addon in addons:
        OrderItem.objects.create(order=order, kind=OrderItem.ADDON, addon=addon, service_name=service_name,
                                 name=f"Add-on: {addon.name}", unit_price=addon.price(currency))
    order.recalculate()

    profile = get_profile(user)
    profile.phone = contact.get("phone", "") or profile.phone
    profile.company = contact.get("company", "") or profile.company
    profile.country = contact.get("country", "") or profile.country
    profile.market = CustomerProfile.MARKET_BANGLADESH if currency == "bdt" else CustomerProfile.MARKET_INTERNATIONAL
    profile.save()
    return order


@transaction.atomic
def create_order_from_quote(quote):
    """Staff action: turn an accepted, priced quote into a payable order for that customer."""
    if not quote.user_id:
        raise CheckoutError("The quote has no customer account. Ask the customer to sign up first.")
    if quote.quoted_amount is None:
        raise CheckoutError("Enter the quoted amount first.")
    order = Order.objects.create(user=quote.user, currency=quote.currency, status=Order.PENDING_PAYMENT,
                                 full_name=quote.full_name, email=quote.email, phone=quote.phone,
                                 notes=quote.brief, quote=quote)
    OrderItem.objects.create(order=order, kind=OrderItem.QUOTE,
                             service_name=quote.service.title if quote.service_id else "Custom project",
                             name=f"Custom quote: {quote.service or 'Custom project'}",
                             unit_price=quote.quoted_amount)
    order.recalculate()
    quote.status = quote.STATUS_ACCEPTED
    quote.save(update_fields=["status"])
    return order

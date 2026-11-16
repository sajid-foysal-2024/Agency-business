"""Build pre-filled WhatsApp links for packages."""
import re
from urllib.parse import quote

from .models import CURRENCIES


def clean_number(number):
    """Keep digits only: '+880 1712-345678' -> '8801712345678'."""
    return re.sub(r"\D", "", number or "")


def whatsapp_url(number, message):
    digits = clean_number(number)
    if not digits:
        return ""
    return f"https://wa.me/{digits}?text={quote(message)}"


def package_message(brand, package, currency, service=None):
    """The inquiry text sent for one package in one currency."""
    if package.is_combo:
        names = ", ".join(s.title for s in package.included_services.all())
        interest = f"I am interested in your {package.name} combo package"
        interest += f" ({names})." if names else "."
    else:
        interest = f"I am interested in your {(service or package.service).title} service."

    price = package.display_price(currency) or "Please share the price"
    lines = [
        f"Hello {brand}!",
        interest,
        f"Package: {package.name}.",
        f"Currency: {CURRENCIES[currency]['code']}.",
        f"Price: {price}.",
        "I would like to discuss this package.",
    ]
    return "\n".join(lines)


def attach_whatsapp_links(packages, site, service=None):
    """Give each package `wa_bdt` / `wa_usd` links (empty when no number is set)."""
    for package in packages:
        for currency in CURRENCIES:
            message = package_message(site.brand_name, package, currency, service)
            setattr(package, f"wa_{currency}", whatsapp_url(site.whatsapp_number, message))
    return packages


def general_whatsapp_url(site, service=None):
    if service:
        message = f"Hello {site.brand_name}!\nI would like to know more about your {service.title} service."
    else:
        message = f"Hello {site.brand_name}!\nI would like to discuss a project."
    return whatsapp_url(site.whatsapp_number, message)

"""Order emails. A failed email never breaks the order; it is only logged."""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _send(subject, body, to):
    if not to:
        return False
    try:
        return bool(send_mail(subject, body, None, [to]))
    except Exception:  # SMTP problems must not affect payments
        logger.exception("Could not send order email to %s", to)
        return False


def send_order_paid_emails(order):
    from home.models import SiteSetting

    site = SiteSetting.load()
    lines = [f"{item.name}: {item.display_line_total}" for item in order.items.all()]
    order_url = settings.SITE_URL + order.get_absolute_url()

    _send(
        f"[{site.brand_name}] Payment received for order {order.number}",
        "\n".join([
            f"Hello {order.full_name},",
            "",
            f"Thank you! We have received your payment for order {order.number}.",
            "",
            *lines,
            f"Total: {order.display_total}",
            "",
            f"View your order and invoice: {order_url}",
            "",
            site.brand_name,
        ]),
        order.email,
    )
    _send(
        f"[{site.brand_name}] New paid order {order.number}",
        "\n".join([f"Order {order.number} was paid.", f"Customer: {order.full_name} <{order.email}>",
                   *lines, f"Total: {order.display_total}", f"Method: {order.payment_method}"]),
        site.notification_email or site.email,
    )

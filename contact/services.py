"""Saving inquiries and sending the notification email."""
import logging
from datetime import timedelta
from urllib.parse import quote

from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from .models import ContactInquiry

logger = logging.getLogger(__name__)

DUPLICATE_WINDOW = timedelta(minutes=10)


def save_inquiry(cleaned_data):
    """Save the inquiry. Returns (inquiry, created).

    The same email + message sent again within a few minutes (double click,
    browser refresh) is treated as the same inquiry instead of a new row.
    """
    recent = ContactInquiry.objects.filter(
        email=cleaned_data["email"],
        message=cleaned_data["message"],
        created_at__gte=timezone.now() - DUPLICATE_WINDOW,
    ).first()
    if recent:
        return recent, False
    fields = {k: v for k, v in cleaned_data.items() if k != "website"}
    return ContactInquiry.objects.create(**fields), True


def notify_agency(inquiry, site, request=None):
    """Email the agency about a new inquiry. Returns True only if the email was sent."""
    recipient = site.notification_email or site.email
    if not recipient:
        return False

    admin_path = reverse("admin:contact_contactinquiry_change", args=[inquiry.pk])
    admin_link = request.build_absolute_uri(admin_path) if request else admin_path
    lines = [
        f"New message from the {site.brand_name} website.",
        "",
        f"Name: {inquiry.full_name}",
        f"Email: {inquiry.email}",
        f"Phone: {inquiry.phone or '-'}",
        f"Service: {inquiry.service or '-'}",
        f"Subject: {inquiry.subject}",
        "",
        inquiry.message,
        "",
        f"Open in admin: {admin_link}",
    ]
    try:
        sent = send_mail(
            subject=f"[{site.brand_name}] New inquiry: {inquiry.subject}",
            message="\n".join(lines),
            from_email=None,  # DEFAULT_FROM_EMAIL
            recipient_list=[recipient],
        )
    except Exception:  # SMTP down, wrong password, etc. The inquiry is still saved.
        logger.exception("Could not send contact notification for inquiry %s", inquiry.pk)
        return False

    if sent:
        ContactInquiry.objects.filter(pk=inquiry.pk).update(notification_sent=True)
    return bool(sent)


def map_urls(address):
    """Google Maps embed + directions links for an address (no API key needed)."""
    if not address:
        return {"embed": "", "directions": ""}
    q = quote(address)
    return {
        "embed": f"https://www.google.com/maps?q={q}&output=embed",
        "directions": f"https://www.google.com/maps/dir/?api=1&destination={q}",
    }

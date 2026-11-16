from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Error, Tags, register


class PaymentsConfig(AppConfig):
    name = "payments"

    def ready(self):
        register(check_payment_settings, Tags.security)


def check_payment_settings(app_configs=None, **kwargs):
    """Stops the site from starting with an unsafe payment setup."""
    errors = []
    mode = getattr(settings, "PAYMENT_MODE", "sandbox")
    if mode not in ("sandbox", "live"):
        errors.append(Error(f"PAYMENT_MODE must be 'sandbox' or 'live', not {mode!r}.", id="payments.E001"))
    if mode == "live":
        if not (settings.SSLCOMMERZ_STORE_ID and settings.SSLCOMMERZ_STORE_PASSWORD):
            errors.append(Error(
                "PAYMENT_MODE=live needs the approved SSLCOMMERZ_STORE_ID and SSLCOMMERZ_STORE_PASSWORD "
                "in the environment.", id="payments.E002"))
        if settings.SSLCOMMERZ_STORE_ID.strip().lower() == "testbox":
            errors.append(Error(
                "SSLCOMMERZ_STORE_ID is the public sandbox sample store (testbox). "
                "Use your approved live store credentials for PAYMENT_MODE=live.", id="payments.E005"))
        if settings.DEBUG:
            errors.append(Error("PAYMENT_MODE=live must not run with DEBUG=True.", id="payments.E003"))
        if not settings.SITE_URL.startswith("https://"):
            errors.append(Error("PAYMENT_MODE=live needs SITE_URL to start with https://.", id="payments.E004"))
    return errors

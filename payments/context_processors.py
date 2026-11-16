from django.conf import settings


def payment_mode(request):
    """{{ payment_sandbox }} is True while no real money can move."""
    return {"payment_sandbox": settings.PAYMENT_MODE != "live"}

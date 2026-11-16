"""Create the payment method rows (texts and on/off switches only, no secrets).

Only the Demo method starts enabled, and it works only in PAYMENT_MODE=sandbox.
SSLCOMMERZ also needs credentials in .env; bank transfer and Payoneer need your
own instructions before you enable them.
"""
from django.db import migrations

METHODS = [
    ("demo", "Demo payment (test only)", True, "bdt,usd",
     "Sandbox mode: simulate success, failure, cancellation or pending. No money moves.", ""),
    ("sslcommerz", "Card, bKash, Nagad (SSLCOMMERZ)", False, "bdt,usd",
     "Pay on the SSLCOMMERZ secure page.", ""),
    ("bank_transfer", "Bank transfer", False, "bdt,usd",
     "Pay by bank transfer. Your order starts after we receive the money.", ""),
    ("payoneer_invoice", "Payoneer payment request", False, "usd",
     "We email you a Payoneer payment request. Pay by card or bank from that email.", ""),
]


def create_methods(apps, schema_editor):
    PaymentMethodConfig = apps.get_model("payments", "PaymentMethodConfig")
    for order, (code, name, enabled, currencies, description, instructions) in enumerate(METHODS):
        PaymentMethodConfig.objects.get_or_create(code=code, defaults={
            "display_name": name, "is_enabled": enabled, "currencies": currencies,
            "description": description, "instructions": instructions, "order": order,
        })


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_methods, migrations.RunPython.noop),
    ]

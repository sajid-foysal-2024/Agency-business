"""Payment brands and which method offers them.

SSLCOMMERZ: Visa, Mastercard (shown on sslcommerz.com), American Express
(priced on sslcommerz.com/pricing), bKash, Nagad, Rocket (SSLCOMMERZ mobile banking).
Payoneer: payment request (client pays by card or US bank). Bank transfer: own bank.
PayPal is not added: it does not operate for businesses in Bangladesh.
Logos are uploaded later in the admin; until then an icon or the name is shown.
"""
from django.db import migrations

BRANDS = [
    ("visa", "Visa", "international", "fa-brands fa-cc-visa"),
    ("mastercard", "Mastercard", "international", "fa-brands fa-cc-mastercard"),
    ("amex", "American Express", "international", "fa-brands fa-cc-amex"),
    ("payoneer", "Payoneer", "international", ""),
    ("bkash", "bKash", "bangladesh", ""),
    ("nagad", "Nagad", "bangladesh", ""),
    ("rocket", "Rocket", "bangladesh", ""),
    ("bank", "Bank transfer", "bangladesh", "fa-solid fa-building-columns"),
]

LINKS = {
    "sslcommerz": ["visa", "mastercard", "amex", "bkash", "nagad", "rocket"],
    "payoneer_invoice": ["payoneer"],
    "bank_transfer": ["bank"],
}


def create_brands(apps, schema_editor):
    PaymentBrand = apps.get_model("payments", "PaymentBrand")
    PaymentMethodConfig = apps.get_model("payments", "PaymentMethodConfig")
    brands = {}
    for order, (code, name, market, icon) in enumerate(BRANDS):
        brands[code], _ = PaymentBrand.objects.get_or_create(
            code=code, defaults={"name": name, "market": market, "icon": icon, "order": order})
    for method_code, codes in LINKS.items():
        method = PaymentMethodConfig.objects.filter(code=method_code).first()
        if method:
            method.brands.add(*[brands[c] for c in codes])


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0003_payment_brands"),
    ]

    operations = [
        migrations.RunPython(create_brands, migrations.RunPython.noop),
    ]

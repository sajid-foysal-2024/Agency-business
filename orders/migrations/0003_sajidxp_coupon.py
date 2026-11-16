"""Create the SAJIDXP coupon chosen by the owner: 15% off, once per customer, no expiry."""
from decimal import Decimal

from django.db import migrations


def create_coupon(apps, schema_editor):
    Coupon = apps.get_model("orders", "Coupon")
    Coupon.objects.get_or_create(code="SAJIDXP", defaults={
        "description": "15% off any package",
        "discount_type": "percent",
        "percent": Decimal("15"),
        "max_uses": None,
        "max_uses_per_customer": 1,
        "is_active": True,
    })


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_coupons"),
    ]

    operations = [
        migrations.RunPython(create_coupon, migrations.RunPython.noop),
    ]

"""Fill in the office address supplied by the owner (only if it is still empty)."""
from django.db import migrations

OFFICE_ADDRESS = (
    "House-698/15, 40 Feet Road, Block-A, Shopnodhara Housing, Bosila, "
    "Mohammadpur, Mohammadpur 1207, Bangladesh."
)


def set_address(apps, schema_editor):
    SiteSetting = apps.get_model("home", "SiteSetting")
    site, _ = SiteSetting.objects.get_or_create(pk=1)
    changed = []
    if not site.address:
        site.address = OFFICE_ADDRESS
        changed.append("address")
    if not site.office_label:
        site.office_label = "OS Agency Office"
        changed.append("office_label")
    if changed:
        site.save(update_fields=changed)


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0008_contact_settings"),
    ]

    operations = [
        migrations.RunPython(set_address, migrations.RunPython.noop),
    ]

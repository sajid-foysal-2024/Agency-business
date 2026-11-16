"""Copy the existing home.Service rows into service.Service (same ids, texts and images)."""
from django.db import migrations
from django.utils.text import slugify


def copy_services(apps, schema_editor):
    OldService = apps.get_model("home", "Service")
    Service = apps.get_model("service", "Service")

    used = set(Service.objects.values_list("slug", flat=True))
    for old in OldService.objects.all().order_by("order", "id"):
        base = slugify(old.title) or "service"
        slug, n = base, 2
        while slug in used:
            slug = f"{base}-{n}"
            n += 1
        used.add(slug)
        Service.objects.create(
            id=old.id,
            title=old.title,
            slug=slug,
            description=old.description,
            image=old.image.name if old.image else "",
            button_text=old.button_text,
            order=old.order,
            is_active=old.is_active,
            created_at=old.created_at,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("service", "0001_initial"),
        ("home", "0006_starter_content"),
    ]

    operations = [
        migrations.RunPython(copy_services, migrations.RunPython.noop),
    ]

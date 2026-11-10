"""Copy the old home.TeamMember rows into Developer so no data is lost."""
from django.db import migrations
from django.utils.text import slugify


def copy_team_members(apps, schema_editor):
    TeamMember = apps.get_model("home", "TeamMember")
    Developer = apps.get_model("developers", "Developer")

    used_slugs = set(Developer.objects.values_list("slug", flat=True))
    for member in TeamMember.objects.all():
        base = slugify(member.name) or "developer"
        slug, n = base, 2
        while slug in used_slugs:
            slug = f"{base}-{n}"
            n += 1
        used_slugs.add(slug)

        Developer.objects.create(
            name=member.name,
            slug=slug,
            designation=member.role,
            photo=member.photo.name if member.photo else "",
            bio=member.bio,
            facebook_url=member.facebook_url,
            x_url=member.x_url,
            instagram_url=member.instagram_url,
            linkedin_url=member.linkedin_url,
            order=member.order,
            is_active=member.is_active,
            created_at=member.created_at,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("developers", "0001_initial"),
        ("home", "0003_site_structure"),
    ]

    operations = [
        migrations.RunPython(copy_team_members, migrations.RunPython.noop),
    ]

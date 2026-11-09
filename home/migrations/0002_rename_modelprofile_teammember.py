from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0001_initial"),
    ]

    operations = [
        migrations.RenameModel(old_name="ModelProfile", new_name="TeamMember"),
    ]

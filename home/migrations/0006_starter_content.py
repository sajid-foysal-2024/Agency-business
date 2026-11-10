"""Starter content for the new home page sections.

Only added when a section is still empty, and everything can be edited or
removed from the admin afterwards. Counters use automatic sources, so they
always show real numbers from the database.
"""
from django.db import migrations

STATS = [
    ("Years Experience", "fa-solid fa-calendar-check", "years"),
    ("Projects Completed", "fa-solid fa-briefcase", "projects"),
    ("Expert Developers", "fa-solid fa-users", "developers"),
    ("Happy Clients", "fa-solid fa-face-smile", "clients"),
]

FEATURES = [
    ("Skilled Team", "fa-solid fa-user-gear",
     "Experienced developers and editors who care about the details of every project."),
    ("Clean, Modern Work", "fa-solid fa-code",
     "Fast, responsive and well-structured websites, apps and videos built with modern tools."),
    ("On-Time Delivery", "fa-solid fa-clock",
     "Clear milestones and regular updates, so you always know where your project stands."),
    ("Ongoing Support", "fa-solid fa-headset",
     "We stay with you after launch to fix issues, add features and help you grow."),
]

PROCESS = [
    ("Discuss", "fa-solid fa-comments", "We listen to your idea, goals and budget."),
    ("Plan & Design", "fa-solid fa-pen-ruler", "We plan the features and design how it will look."),
    ("Build", "fa-solid fa-laptop-code", "We develop, test and share progress with you."),
    ("Launch & Support", "fa-solid fa-rocket", "We go live and keep supporting you after launch."),
]


def add_starter_content(apps, schema_editor):
    Stat = apps.get_model("home", "Stat")
    Feature = apps.get_model("home", "Feature")
    ProcessStep = apps.get_model("home", "ProcessStep")

    if not Stat.objects.exists():
        for i, (label, icon, source) in enumerate(STATS, start=1):
            Stat.objects.create(label=label, icon=icon, source=source, suffix="+", order=i)

    if not Feature.objects.exists():
        for i, (title, icon, text) in enumerate(FEATURES, start=1):
            Feature.objects.create(title=title, icon=icon, text=text, order=i)

    if not ProcessStep.objects.exists():
        for i, (title, icon, text) in enumerate(PROCESS, start=1):
            ProcessStep.objects.create(title=title, icon=icon, text=text, order=i)


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0005_professional_home_sections"),
    ]

    operations = [
        migrations.RunPython(add_starter_content, migrations.RunPython.noop),
    ]

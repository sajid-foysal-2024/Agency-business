"""Read-only database queries for the home app.

Views call these functions instead of querying models directly, so the
"what data does this page need" logic lives in one place.
"""
from django.utils import timezone

from developers.models import ClientReview, Developer, Project
from developers.selectors import get_home_page_developers

from .models import (About, ClientLogo, Feature, HeroSlide, HomePage, ProcessStep,
                     Service, SiteSetting, Stat, Testimonial)


def get_active_slides():
    return HeroSlide.objects.filter(is_active=True)


def get_about():
    return About.objects.prefetch_related("points").filter(pk=1, is_active=True).first()


def get_active_services():
    return Service.objects.filter(is_active=True)


def get_active_testimonials():
    return Testimonial.objects.filter(is_active=True)


def get_featured_projects(limit):
    return (Project.objects.active()
            .filter(is_featured=True, developer__is_active=True)
            .select_related("developer")
            .order_by("order", "-id")[:limit])


def get_stats():
    """Active counters with their final number filled in (`stat.number`)."""
    founded = SiteSetting.load().founded_year
    auto_values = {
        Stat.SOURCE_YEARS: lambda: max(timezone.now().year - founded, 1) if founded else 0,
        Stat.SOURCE_PROJECTS: lambda: Project.objects.active().filter(developer__is_active=True).count(),
        Stat.SOURCE_DEVELOPERS: lambda: Developer.objects.active().count(),
        Stat.SOURCE_CLIENTS: lambda: (ClientReview.objects.filter(is_active=True).count()
                                      + Testimonial.objects.filter(is_active=True).count()),
    }
    stats = []
    for stat in Stat.objects.filter(is_active=True):
        stat.number = auto_values[stat.source]() if stat.source in auto_values else stat.value
        if stat.number:  # never show a "0" counter
            stats.append(stat)
    return stats


def get_home_page_context():
    """Everything the home page template needs."""
    page = HomePage.load()
    return {
        "page": page,
        "slides": get_active_slides(),
        "stats": get_stats() if page.show_stats else [],
        "about": get_about(),
        "services": get_active_services(),
        "features": Feature.objects.filter(is_active=True),
        "featured_projects": get_featured_projects(page.works_limit),
        "process_steps": ProcessStep.objects.filter(is_active=True),
        "team_members": get_home_page_developers(),
        "testimonials": get_active_testimonials(),
        "client_logos": ClientLogo.objects.filter(is_active=True),
    }

"""Read-only database queries for the home app.

Views call these functions instead of querying models directly, so the
"what data does this page need" logic lives in one place.
"""
from .models import About, HeroSlide, HomePage, Service, TeamMember, Testimonial


def get_active_slides():
    return HeroSlide.objects.filter(is_active=True)


def get_about():
    about = About.objects.prefetch_related("points").filter(pk=1, is_active=True).first()
    return about


def get_active_services():
    return Service.objects.filter(is_active=True)


def get_active_team_members():
    return TeamMember.objects.filter(is_active=True)


def get_active_testimonials():
    return Testimonial.objects.filter(is_active=True)


def get_home_page_context():
    """Everything the home page template needs."""
    return {
        "page": HomePage.load(),
        "slides": get_active_slides(),
        "about": get_about(),
        "services": get_active_services(),
        "team_members": get_active_team_members(),
        "testimonials": get_active_testimonials(),
    }

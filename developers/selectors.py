"""Read-only database queries for the developers app."""
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404

from .models import ClientReview, Developer, Project

PORTFOLIO_WORKS_LIMIT = 4


def get_active_developers():
    return Developer.objects.active().prefetch_related("skills")


def get_home_page_developers():
    return Developer.objects.on_home_page()


def get_active_developer(slug):
    return get_object_or_404(Developer.objects.active(), slug=slug)


def get_portfolio_developer(slug):
    """One active developer with everything their portfolio page needs."""
    queryset = Developer.objects.active().prefetch_related(
        "skills",
        "services",
        Prefetch("projects", queryset=Project.objects.active(), to_attr="active_projects"),
        Prefetch("reviews", queryset=ClientReview.objects.filter(is_active=True), to_attr="active_reviews"),
    )
    return get_object_or_404(queryset, slug=slug)


def get_developer_projects(developer, category=None):
    projects = developer.projects.active()
    if category:
        projects = projects.filter(category__iexact=category)
    return projects


def get_project_categories(developer):
    categories = developer.projects.active().exclude(category="").values_list("category", flat=True)
    return sorted(set(categories), key=str.lower)


def get_project(developer, project_slug):
    return get_object_or_404(developer.projects.active().select_related("developer"), slug=project_slug)


def get_neighbour_projects(project):
    """The previous and next project of the same developer (for page navigation)."""
    projects = list(project.developer.projects.active().only("id", "slug", "title", "developer_id"))
    ids = [p.id for p in projects]
    index = ids.index(project.id)
    previous_project = projects[index - 1] if index > 0 else None
    next_project = projects[index + 1] if index < len(projects) - 1 else None
    return previous_project, next_project

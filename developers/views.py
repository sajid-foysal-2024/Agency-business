from urllib.parse import urlencode

from django.urls import reverse
from django.views.generic import DetailView, ListView

from . import selectors


def crumb(label, url=None):
    return {"label": label, "url": url}


class DeveloperListView(ListView):
    """All developers working at the agency."""

    template_name = "developers/developer_list.html"
    context_object_name = "developers"
    paginate_by = 12

    def get_queryset(self):
        return selectors.get_active_developers()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [crumb("Developers")]
        return context


class DeveloperDetailView(DetailView):
    """A developer's full portfolio page."""

    template_name = "developers/developer_detail.html"
    context_object_name = "developer"

    def get_object(self, queryset=None):
        return selectors.get_portfolio_developer(self.kwargs["slug"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        projects = self.object.active_projects
        context["works"] = projects[:selectors.PORTFOLIO_WORKS_LIMIT]
        context["has_more_works"] = len(projects) > selectors.PORTFOLIO_WORKS_LIMIT
        return context


class DeveloperWorksView(ListView):
    """Every project of one developer, with an optional category filter."""

    template_name = "developers/project_list.html"
    context_object_name = "projects"
    paginate_by = 8

    def get_queryset(self):
        self.developer = selectors.get_active_developer(self.kwargs["slug"])
        self.category = self.request.GET.get("category", "").strip()
        return selectors.get_developer_projects(self.developer, self.category)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["developer"] = self.developer
        context["categories"] = selectors.get_project_categories(self.developer)
        context["current_category"] = self.category
        context["extra_query"] = urlencode({"category": self.category}) + "&" if self.category else ""
        context["breadcrumbs"] = [
            crumb("Developers", reverse("developers:list")),
            crumb(self.developer.name, self.developer.get_absolute_url()),
            crumb("Works"),
        ]
        return context


class ProjectDetailView(DetailView):
    template_name = "developers/project_detail.html"
    context_object_name = "project"

    def get_object(self, queryset=None):
        developer = selectors.get_active_developer(self.kwargs["slug"])
        return selectors.get_project(developer, self.kwargs["project_slug"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        developer = self.object.developer
        context["developer"] = developer
        context["previous_project"], context["next_project"] = selectors.get_neighbour_projects(self.object)
        context["breadcrumbs"] = [
            crumb("Developers", reverse("developers:list")),
            crumb(developer.name, developer.get_absolute_url()),
            crumb("Works", reverse("developers:works", args=[developer.slug])),
            crumb(self.object.title),
        ]
        return context

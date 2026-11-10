from django.urls import path

from . import views

app_name = "developers"

urlpatterns = [
    path("", views.DeveloperListView.as_view(), name="list"),
    path("<slug:slug>/", views.DeveloperDetailView.as_view(), name="detail"),
    path("<slug:slug>/works/", views.DeveloperWorksView.as_view(), name="works"),
    path("<slug:slug>/works/<slug:project_slug>/", views.ProjectDetailView.as_view(), name="project"),
]

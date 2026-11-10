from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from core.admin_utils import OrderedAdmin, image_preview

from .models import ClientReview, Developer, DeveloperService, Project, Skill


class SkillInline(admin.TabularInline):
    model = Skill
    extra = 1
    fields = ("name", "percentage", "order")


class DeveloperServiceInline(admin.TabularInline):
    model = DeveloperService
    extra = 1
    fields = ("title", "description", "icon", "order")


class ProjectInline(admin.TabularInline):
    """Quick overview of projects; open a project to edit all its details."""

    model = Project
    extra = 0
    fields = ("title", "category", "is_featured", "order", "is_active")
    show_change_link = True


class ClientReviewInline(admin.StackedInline):
    model = ClientReview
    extra = 0
    fields = (("client_name", "client_role"), "message", "photo", ("order", "is_active"))


@admin.register(Developer)
class DeveloperAdmin(OrderedAdmin):
    list_display = ("name", image_preview("photo"), "designation", "project_count",
                    "is_available", "show_on_home", "order", "is_active", "portfolio_link")
    list_editable = ("is_available", "show_on_home", "order", "is_active")
    list_filter = ("is_active", "is_available", "show_on_home")
    search_fields = ("name", "designation", "email")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [SkillInline, DeveloperServiceInline, ProjectInline, ClientReviewInline]
    fieldsets = (
        ("Basic info", {"fields": ("name", "slug", "designation", "photo")}),
        ("Portfolio", {"fields": ("headline", "bio", "cv")}),
        ("Work", {"fields": ("experience_years", "joined_on", "is_available",
                             "show_on_home", "order", "is_active")}),
        ("Contact", {"fields": ("email", "phone", "location")}),
        ("Social links", {
            "fields": ("github_url", "linkedin_url", "facebook_url", "x_url",
                       "instagram_url", "behance_url", "dribbble_url", "website_url"),
            "description": "Leave a link blank to hide it.",
        }),
        ("Let's Talk section", {"fields": ("cta_title", "cta_text"), "classes": ("collapse",)}),
        ("Info", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_project_count=Count("projects"))

    @admin.display(description="Projects", ordering="_project_count")
    def project_count(self, obj):
        return obj._project_count

    @admin.display(description="Portfolio")
    def portfolio_link(self, obj):
        if not obj.pk or not obj.is_active:
            return "-"
        return format_html('<a href="{}" target="_blank">View</a>', obj.get_absolute_url())


@admin.register(Project)
class ProjectAdmin(OrderedAdmin):
    list_display = ("title", image_preview("image"), "developer", "category",
                    "is_featured", "order", "is_active")
    list_editable = ("is_featured", "order", "is_active")
    list_filter = ("is_active", "is_featured", "developer", "category")
    search_fields = ("title", "category", "technologies", "developer__name")
    autocomplete_fields = ("developer",)
    prepopulated_fields = {"slug": ("title",)}
    fieldsets = (
        (None, {"fields": ("developer", "title", "slug", "category", "image", "summary", "description")}),
        ("Details", {"fields": ("client", "technologies", "completed_on", "live_url", "source_url")}),
        ("Display", {"fields": ("is_featured", "order", "is_active")}),
    )

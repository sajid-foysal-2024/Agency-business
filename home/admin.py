from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from .models import (About, AboutPoint, HeroSlide, HomePage, Service,
                     SiteSetting, Subscriber, TeamMember, Testimonial)

admin.site.site_header = "Agency Admin"
admin.site.site_title = "Agency Admin"
admin.site.index_title = "Website content"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def image_preview(field_name, size=60):
    """Build a small thumbnail column for list pages."""

    @admin.display(description="Preview")
    def _preview(obj):
        image = getattr(obj, field_name)
        if not image:
            return "-"
        return format_html(
            '<img src="{}" style="height:{}px;width:{}px;object-fit:cover;border-radius:6px;">',
            image.url, size, size,
        )

    return _preview


class SingletonAdmin(admin.ModelAdmin):
    """Admin for one-row models: the list page opens the edit form directly."""

    def has_add_permission(self, request):
        return not self.model.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = self.model.load()
        opts = self.model._meta
        return redirect(reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk]))


class OrderedAdmin(admin.ModelAdmin):
    list_editable = ("order", "is_active")
    list_filter = ("is_active",)
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# Site & page settings
# ---------------------------------------------------------------------------

@admin.register(SiteSetting)
class SiteSettingAdmin(SingletonAdmin):
    fieldsets = (
        ("Branding", {"fields": ("brand_name", "tagline", "brand_icon", "logo", "favicon")}),
        ("SEO", {"fields": ("meta_description", "meta_keywords")}),
        ("Contact", {"fields": ("email", "phone", "address")}),
        ("Social links", {
            "fields": ("facebook_url", "x_url", "instagram_url", "linkedin_url", "youtube_url"),
            "description": "Leave a link blank to hide its icon.",
        }),
        ("Footer", {"fields": ("copyright_name",)}),
    )


@admin.register(HomePage)
class HomePageAdmin(SingletonAdmin):
    fieldsets = (
        ("SEO", {"fields": ("meta_title",)}),
        ("Services section", {"fields": ("services_subtitle", "services_title")}),
        ("Team section", {"fields": ("team_subtitle", "team_title")}),
        ("Testimonials section", {"fields": ("testimonials_subtitle", "testimonials_title")}),
        ("Newsletter section", {"fields": (
            "show_newsletter", "newsletter_subtitle", "newsletter_title",
            "newsletter_text", "newsletter_button_text",
        )}),
    )


class AboutPointInline(admin.TabularInline):
    model = AboutPoint
    extra = 1
    fields = ("text", "order")


@admin.register(About)
class AboutAdmin(SingletonAdmin):
    inlines = [AboutPointInline]
    fieldsets = (
        (None, {"fields": ("is_active", "subtitle", "title", "description", "image")}),
        ("Buttons", {
            "fields": ("primary_button_text", "primary_button_link",
                       "secondary_button_text", "secondary_button_link"),
            "description": "Leave a button's text blank to hide it.",
        }),
    )


# ---------------------------------------------------------------------------
# Lists of content
# ---------------------------------------------------------------------------

@admin.register(HeroSlide)
class HeroSlideAdmin(OrderedAdmin):
    list_display = ("title", image_preview("image"), "subtitle", "order", "is_active")
    search_fields = ("title", "subtitle")


@admin.register(Service)
class ServiceAdmin(OrderedAdmin):
    list_display = ("title", image_preview("image"), "order", "is_active")
    search_fields = ("title", "description")


@admin.register(TeamMember)
class TeamMemberAdmin(OrderedAdmin):
    list_display = ("name", image_preview("photo"), "role", "order", "is_active")
    search_fields = ("name", "role")
    fieldsets = (
        (None, {"fields": ("name", "role", "photo", "bio", "order", "is_active")}),
        ("Social links", {"fields": ("facebook_url", "x_url", "instagram_url", "linkedin_url")}),
        ("Info", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(Testimonial)
class TestimonialAdmin(OrderedAdmin):
    list_display = ("name", image_preview("photo"), "profession", "order", "is_active")
    search_fields = ("name", "profession", "message")


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("email",)
    readonly_fields = ("created_at",)

from django.contrib import admin

from core.admin_utils import OrderedAdmin, SingletonAdmin, image_preview

from .models import (About, AboutPoint, ClientLogo, Feature, HeroSlide, HomePage,
                     ProcessStep, Service, SiteSetting, Stat, Subscriber, Testimonial)

admin.site.site_header = "Agency Admin"
admin.site.site_title = "Agency Admin"
admin.site.index_title = "Website content"


# ---------------------------------------------------------------------------
# Site & page settings
# ---------------------------------------------------------------------------

@admin.register(SiteSetting)
class SiteSettingAdmin(SingletonAdmin):
    fieldsets = (
        ("Branding", {"fields": ("brand_name", "tagline", "brand_icon", "logo", "favicon", "founded_year")}),
        ("Header button", {"fields": ("header_button_text", "header_button_link")}),
        ("SEO", {"fields": ("meta_description", "meta_keywords")}),
        ("Contact", {"fields": ("email", "phone", "address")}),
        ("Social links", {
            "fields": ("facebook_url", "x_url", "instagram_url", "linkedin_url", "youtube_url"),
            "description": "Leave a link blank to hide its icon.",
        }),
        ("Footer", {"fields": ("about_short", "copyright_name")}),
    )


@admin.register(HomePage)
class HomePageAdmin(SingletonAdmin):
    fieldsets = (
        ("SEO", {"fields": ("meta_title",)}),
        ("Counters", {
            "fields": ("show_stats",),
            "description": "Add the counters themselves under Home > Stats.",
        }),
        ("Services section", {"fields": ("services_subtitle", "services_title")}),
        ("Why choose us section", {"fields": ("features_subtitle", "features_title", "features_text")}),
        ("Recent works section", {
            "fields": ("works_subtitle", "works_title", "works_limit"),
            "description": "Shows developer projects marked \"Is featured\".",
        }),
        ("Process section", {"fields": ("process_subtitle", "process_title")}),
        ("Team section", {
            "fields": ("team_subtitle", "team_title", "team_button_text"),
            "description": "Developers marked \"Show on home page\" appear in this section.",
        }),
        ("Testimonials section", {"fields": ("testimonials_subtitle", "testimonials_title")}),
        ("Client logos section", {"fields": ("clients_subtitle", "clients_title")}),
        ("Call-to-action banner", {"fields": (
            "show_cta", "cta_title", "cta_text", "cta_button_text", "cta_button_link",
        )}),
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


@admin.register(Stat)
class StatAdmin(OrderedAdmin):
    list_display = ("label", "source", "value", "suffix", "order", "is_active")
    fields = ("label", "icon", "source", "value", "suffix", "order", "is_active")


@admin.register(Feature)
class FeatureAdmin(OrderedAdmin):
    list_display = ("title", "icon", "order", "is_active")
    search_fields = ("title", "text")


@admin.register(ProcessStep)
class ProcessStepAdmin(OrderedAdmin):
    list_display = ("title", "icon", "order", "is_active")


@admin.register(ClientLogo)
class ClientLogoAdmin(OrderedAdmin):
    list_display = ("name", image_preview("logo"), "website", "order", "is_active")
    search_fields = ("name",)


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

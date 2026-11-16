from django import forms
from django.contrib import admin, messages
from django.db.models import Count
from django.utils.html import format_html

from core.admin_utils import OrderedAdmin, image_preview

from .models import AddOn, FAQ, Package, PackageFeature, QuoteRequest, Service, ServiceCategory, ServiceOffering


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(OrderedAdmin):
    list_display = ("name", "service_count", "order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)
    fields = ("name", "slug", "description", "order", "is_active")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_service_count=Count("services"))

    @admin.display(description="Services", ordering="_service_count")
    def service_count(self, obj):
        return obj._service_count


class ServiceOfferingInline(admin.TabularInline):
    model = ServiceOffering
    extra = 1
    fields = ("title", "description", "icon", "order")


class SinglePackageInline(admin.TabularInline):
    """Overview of this service's single packages. Open one to edit features and prices."""

    model = Package
    fk_name = "service"
    extra = 0
    fields = ("name", "price_bdt", "price_usd", "is_popular", "order", "is_active")
    show_change_link = True
    verbose_name = "Single package"
    verbose_name_plural = "Single packages (open a package to add its features)"

    def get_queryset(self, request):
        return super().get_queryset(request).filter(package_type=Package.SINGLE)


class AddOnInline(admin.TabularInline):
    model = AddOn
    extra = 0
    fields = ("name", "description", "price_bdt", "price_usd", "order", "is_active")
    verbose_name_plural = "Add-ons for this service (add-ons for every service are under Service > Add-ons)"


class FAQInline(admin.TabularInline):
    model = FAQ
    extra = 1
    fields = ("question", "answer", "order", "is_active")


@admin.register(Service)
class ServiceAdmin(OrderedAdmin):
    list_display = ("title", image_preview("image"), "category", "package_count",
                    "order", "is_active", "page_link")
    list_filter = ("is_active", "category")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [ServiceOfferingInline, SinglePackageInline, AddOnInline, FAQInline]
    fieldsets = (
        (None, {"fields": ("title", "slug", "category", "icon", "description", "image",
                           "button_text", "order", "is_active")}),
        ("Details page", {"fields": ("hero_subtitle", "hero_image", "overview_title", "overview",
                                     "offerings_title")}),
        ("Marketplace", {"fields": ("deliverables", "delivery_time", "allow_custom_quote")}),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_package_count=Count("packages"))

    @admin.display(description="Packages", ordering="_package_count")
    def package_count(self, obj):
        return obj._package_count

    @admin.display(description="Page")
    def page_link(self, obj):
        if not obj.pk or not obj.is_active:
            return "-"
        return format_html('<a href="{}" target="_blank">View</a>', obj.get_absolute_url())


class PackageFeatureInline(admin.TabularInline):
    model = PackageFeature
    extra = 3
    fields = ("text", "is_included", "order")


class PackageAdminForm(forms.ModelForm):
    class Meta:
        model = Package
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("package_type") == Package.COMBO:
            included = cleaned.get("included_services")
            if included is not None and included.count() < 2:
                self.add_error("included_services", "A combo package needs at least 2 services.")
        return cleaned


@admin.register(Package)
class PackageAdmin(OrderedAdmin):
    form = PackageAdminForm
    list_display = ("name", "package_type", "billing_type", "service", "price_bdt", "price_usd", "is_demo",
                    "is_popular", "is_featured", "order", "is_active")
    list_editable = ("is_popular", "is_featured", "order", "is_active")
    list_filter = ("is_demo", "package_type", "billing_type", "is_active", "is_popular", "is_featured", "service")
    search_fields = ("name", "tagline", "service__title")
    filter_horizontal = ("included_services",)
    inlines = [PackageFeatureInline]
    fieldsets = (
        ("Package", {"fields": ("package_type", "billing_type", "service", "included_services", "name", "tagline")}),
        ("Prices", {
            "fields": (("price_bdt", "price_usd"), ("regular_price_bdt", "regular_price_usd"),
                       "price_note", "discount_text", "delivery_time"),
            "description": "Each currency is separate. Leave a price blank to show \"Price on request\".",
        }),
        ("Display", {"fields": ("is_popular", "is_featured", "button_text", "order", "is_active")}),
    )


@admin.register(FAQ)
class FAQAdmin(OrderedAdmin):
    list_display = ("question", "service", "is_demo", "order", "is_active")
    list_filter = ("is_demo", "is_active", "service")
    search_fields = ("question", "answer")
    fields = ("service", "question", "answer", "order", "is_active")


@admin.register(AddOn)
class AddOnAdmin(OrderedAdmin):
    list_display = ("name", "service", "price_bdt", "price_usd", "is_demo", "order", "is_active")
    list_filter = ("is_demo", "is_active", "service")
    search_fields = ("name", "description")
    fields = ("service", "name", "description", "price_bdt", "price_usd", "order", "is_active")


@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "service", "currency", "budget", "status", "quoted_amount", "created_at")
    list_editable = ("status",)
    list_filter = ("status", "service", "currency", "created_at")
    search_fields = ("full_name", "email", "brief", "budget")
    readonly_fields = ("user", "full_name", "email", "phone", "service", "budget", "brief", "created_at")
    fields = ("user", "full_name", "email", "phone", "service", "budget", "brief", "currency", "status",
              "quoted_amount", "admin_note", "created_at")
    actions = ["create_order"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Create a payable order from the quote")
    def create_order(self, request, queryset):
        from orders.services import CheckoutError, create_order_from_quote
        for quote in queryset:
            try:
                order = create_order_from_quote(quote)
                self.message_user(request, f"Order {order.number} created for {quote.full_name}. "
                                           "They can pay it from My Orders.")
            except CheckoutError as exc:
                self.message_user(request, f"{quote}: {exc}", messages.ERROR)


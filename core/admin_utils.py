"""Reusable admin helpers."""
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html


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

from django.contrib import admin

from .models import ContactInquiry


@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "phone", "subject", "service", "status", "created_at")
    list_editable = ("status",)
    list_filter = ("status", "service", "created_at")
    search_fields = ("full_name", "email", "phone", "subject", "message")
    date_hierarchy = "created_at"
    list_per_page = 25
    readonly_fields = ("full_name", "email", "phone", "subject", "service", "message",
                       "notification_sent", "created_at", "updated_at")
    fieldsets = (
        ("Customer", {"fields": ("full_name", "email", "phone")}),
        ("Message", {"fields": ("subject", "service", "message")}),
        ("Follow-up", {"fields": ("status", "admin_note")}),
        ("Info", {"fields": ("notification_sent", "created_at", "updated_at"), "classes": ("collapse",)}),
    )
    actions = ["mark_contacted", "mark_completed"]

    def has_add_permission(self, request):
        return False  # inquiries only come from the website form

    @admin.action(description="Mark selected as contacted")
    def mark_contacted(self, request, queryset):
        updated = queryset.update(status=ContactInquiry.STATUS_CONTACTED)
        self.message_user(request, f"{updated} inquiry(s) marked as contacted.")

    @admin.action(description="Mark selected as completed")
    def mark_completed(self, request, queryset):
        updated = queryset.update(status=ContactInquiry.STATUS_COMPLETED)
        self.message_user(request, f"{updated} inquiry(s) marked as completed.")

from decimal import Decimal

from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Payment, PaymentBrand, PaymentEvent, PaymentMethodConfig, Refund
from .providers import get_provider
from .services import PaymentError, apply_result, refund_payment

STATUS_COLORS = {"succeeded": "#1e8e3e", "pending": "#b26a00", "initiated": "#666", "failed": "#c5221f",
                 "cancelled": "#666", "refunded": "#6a1b9a"}


def badge(value, label):
    return format_html('<span style="padding:2px 8px;border-radius:10px;color:#fff;background:{}">{}</span>',
                       STATUS_COLORS.get(value, "#666"), label)


@admin.register(PaymentMethodConfig)
class PaymentMethodConfigAdmin(admin.ModelAdmin):
    list_display = ("display_name", "code", "is_enabled", "currencies", "ready", "order")
    list_editable = ("is_enabled", "order")
    fields = ("code", "display_name", "is_enabled", "currencies", "description", "instructions", "brands", "order")
    readonly_fields = ("code",)
    filter_horizontal = ("brands",)

    def has_add_permission(self, request):
        return False  # methods are defined in code (providers/__init__.py)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Ready to use", boolean=True)
    def ready(self, obj):
        return get_provider(obj.code, obj).is_configured()


@admin.register(PaymentBrand)
class PaymentBrandAdmin(admin.ModelAdmin):
    list_display = ("name", "logo_preview", "market", "methods_list", "order", "is_active")
    list_editable = ("order", "is_active")
    list_filter = ("market", "is_active")
    fields = ("name", "code", "market", "logo", "icon", "order", "is_active")
    prepopulated_fields = {"code": ("name",)}

    @admin.display(description="Logo")
    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="height:28px;background:#fff;padding:2px 6px;border-radius:6px">',
                               obj.logo.url)
        if obj.icon:
            return format_html('<i class="{}"></i> (icon)', obj.icon)
        return "name only"

    @admin.display(description="Shown for")
    def methods_list(self, obj):
        return ", ".join(m.display_name for m in obj.methods.all()) or "-"


class RefundInline(admin.TabularInline):
    model = Refund
    extra = 0
    can_delete = False
    fields = ("amount", "status", "reason", "provider_refund_id", "created_by", "created_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class EventInline(admin.TabularInline):
    model = PaymentEvent
    extra = 0
    can_delete = False
    fields = ("event_id", "signature_valid", "result", "received_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "order", "provider", "display_amount", "status_badge", "is_sandbox", "created_at")
    list_filter = ("status", "provider", "is_sandbox", "currency", "created_at")
    search_fields = ("reference", "order__number", "order__email", "provider_transaction_id")
    date_hierarchy = "created_at"
    readonly_fields = ("order", "provider", "is_sandbox", "reference", "amount", "currency", "status",
                       "provider_transaction_id", "provider_session", "raw_response", "failure_reason",
                       "created_at", "updated_at", "verified_at")
    inlines = [RefundInline, EventInline]
    actions = ["mark_received", "refund_full"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return badge(obj.status, obj.get_status_display())

    @admin.action(description="Mark payment received (manual methods only)")
    def mark_received(self, request, queryset):
        done = 0
        for payment in queryset:
            if not get_provider(payment.provider).is_manual:
                self.message_user(request, f"{payment}: online payments are confirmed by the provider, not by hand.",
                                  messages.ERROR)
                continue
            if payment.status in Payment.OPEN:
                apply_result(payment, Payment.SUCCEEDED, confirmed_by_staff=True,
                             raw={"confirmed_by": request.user.get_username()})
                done += 1
        if done:
            self.message_user(request, f"{done} payment(s) marked as received. Orders are now Paid.")

    @admin.action(description="Refund the full amount")
    def refund_full(self, request, queryset):
        for payment in queryset:
            left = payment.amount - sum((r.amount for r in payment.refunds.exclude(status="failed")), Decimal("0"))
            try:
                refund = refund_payment(payment, left, "Full refund from admin", request.user)
                self.message_user(request, f"{payment}: refund {refund.get_status_display().lower()}.")
            except PaymentError as exc:
                self.message_user(request, f"{payment}: {exc}", messages.ERROR)


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "provider", "payment", "signature_valid", "result", "received_at")
    list_filter = ("provider", "signature_valid")
    search_fields = ("event_id", "payment__reference")
    readonly_fields = ("provider", "event_id", "payment", "payload", "signature_valid", "result", "received_at")

    def has_add_permission(self, request):
        return False


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("payment", "display_amount", "status", "reason", "created_by", "created_at")
    list_filter = ("status",)
    search_fields = ("payment__reference", "payment__order__number")
    readonly_fields = ("payment", "amount", "reason", "status", "provider_refund_id", "raw_response",
                       "created_by", "created_at")

    def has_add_permission(self, request):
        return False

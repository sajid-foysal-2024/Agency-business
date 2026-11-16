from django.contrib import admin
from django.utils.html import format_html

from payments.models import Payment

from .models import Coupon, CustomerProfile, Invoice, Order, OrderItem

ORDER_COLORS = {"draft": "#666", "pending_payment": "#b26a00", "payment_processing": "#b26a00", "paid": "#1e8e3e",
                "failed": "#c5221f", "cancelled": "#666", "refunded": "#6a1b9a", "in_progress": "#1a73e8",
                "completed": "#137333"}


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("__str__", "email", "phone", "company", "country", "market", "order_count", "created_at")
    list_filter = ("market", "country")
    search_fields = ("user__email", "user__first_name", "user__last_name", "phone", "company")

    @admin.display(ordering="user__email")
    def email(self, obj):
        return obj.user.email

    @admin.display(description="Orders")
    def order_count(self, obj):
        return obj.user.orders.count()


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ("kind", "name", "billing_type", "unit_price", "regular_price", "quantity")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ("reference", "provider", "amount", "currency", "status", "is_sandbox", "created_at")
    readonly_fields = fields
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "full_name", "email", "display_total", "status_badge", "payment_method", "created_at")
    list_filter = ("status", "currency", "payment_method", "coupon", "created_at")
    search_fields = ("number", "full_name", "email", "phone", "company", "coupon_code")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline, PaymentInline]
    readonly_fields = ("number", "user", "currency", "subtotal", "total", "payment_method", "quote",
                       "coupon", "coupon_code", "created_at", "updated_at", "paid_at")
    fieldsets = (
        (None, {"fields": ("number", "user", "status", "currency", "payment_method", "quote")}),
        ("Customer", {"fields": ("full_name", "email", "phone", "company", "country", "notes")}),
        ("Amounts", {"fields": ("subtotal", "coupon_code", "discount", "tax", "total"),
                     "description": "Discount and tax can be changed only before payment starts. Save to recalculate."}),
        ("Internal", {"fields": ("admin_note", "created_at", "updated_at", "paid_at")}),
    )
    actions = ["mark_in_progress", "mark_completed"]

    def has_delete_permission(self, request, obj=None):
        return False  # keep the transaction history

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.status not in (Order.DRAFT, Order.PENDING_PAYMENT):
            fields += ["discount", "tax"]
        return fields

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if {"discount", "tax"} & set(form.changed_data):
            obj.recalculate()

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return format_html('<span style="padding:2px 8px;border-radius:10px;color:#fff;background:{}">{}</span>',
                           ORDER_COLORS.get(obj.status, "#666"), obj.get_status_display())

    @admin.display(description="Total", ordering="total")
    def display_total(self, obj):
        return obj.display_total

    @admin.action(description="Mark paid orders as In Progress")
    def mark_in_progress(self, request, queryset):
        updated = queryset.filter(status=Order.PAID).update(status=Order.IN_PROGRESS)
        self.message_user(request, f"{updated} order(s) moved to In Progress (only Paid orders can move).")

    @admin.action(description="Mark orders as Completed")
    def mark_completed(self, request, queryset):
        updated = queryset.filter(status__in=[Order.PAID, Order.IN_PROGRESS]).update(status=Order.COMPLETED)
        self.message_user(request, f"{updated} order(s) marked Completed.")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "order", "status", "issue_date", "due_date", "total")
    list_filter = ("status", "issue_date")
    search_fields = ("number", "order__number", "order__email")
    readonly_fields = ("number", "order")

    @admin.display(description="Amount")
    def total(self, obj):
        return obj.order.display_total


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "is_active", "valid_until", "uses", "max_uses", "max_uses_per_customer")
    list_editable = ("is_active",)
    list_filter = ("is_active", "discount_type")
    search_fields = ("code", "description")
    fieldsets = (
        (None, {"fields": ("code", "description", "is_active")}),
        ("Discount", {"fields": ("discount_type", "percent", ("amount_bdt", "amount_usd")),
                      "description": "Percentage coupons work in both currencies. Fixed coupons work only in the "
                                     "currencies that have an amount."}),
        ("Limits", {"fields": (("min_order_bdt", "min_order_usd"), ("valid_from", "valid_until"),
                               "max_uses", "max_uses_per_customer")}),
    )

    @admin.display(description="Discount")
    def label(self, obj):
        return obj.label

    @admin.display(description="Times used")
    def uses(self, obj):
        return obj.orders.filter(status__in=Order.COUPON_USED).count()


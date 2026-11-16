import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from service.models import CURRENCIES, format_price

CURRENCY_CHOICES = [("bdt", "BDT (৳)"), ("usd", "USD ($)")]


class CustomerProfile(models.Model):
    """Extra details for a customer. Login itself is Django's built-in User."""

    MARKET_INTERNATIONAL = "international"
    MARKET_BANGLADESH = "bangladesh"
    MARKET_CHOICES = [(MARKET_INTERNATIONAL, "International (USD)"), (MARKET_BANGLADESH, "Bangladesh (BDT)")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="customer_profile", on_delete=models.CASCADE)
    phone = models.CharField(max_length=30, blank=True)
    company = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=60, blank=True)
    market = models.CharField(max_length=20, choices=MARKET_CHOICES, default=MARKET_INTERNATIONAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

    def __str__(self):
        return self.user.get_full_name() or self.user.get_username()

    @property
    def preferred_currency(self):
        return "bdt" if self.market == self.MARKET_BANGLADESH else "usd"


def new_order_number():
    """Short, unguessable public order number, e.g. OSA-7K2Q9XWD."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "OSA-" + "".join(secrets.choice(alphabet) for _ in range(8))


class Coupon(models.Model):
    """A discount code customers enter on the review step."""

    PERCENT = "percent"
    FIXED = "fixed"
    TYPE_CHOICES = [(PERCENT, "Percentage of the subtotal"), (FIXED, "Fixed amount per currency")]

    code = models.CharField(max_length=30, unique=True, help_text="Customers type this. Not case-sensitive.")
    description = models.CharField(max_length=150, blank=True)
    discount_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=PERCENT)
    percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                  validators=[MinValueValidator(0), MaxValueValidator(100)],
                                  help_text="For percentage coupons, e.g. 15 for 15%.")
    amount_bdt = models.DecimalField("Fixed amount (BDT)", max_digits=12, decimal_places=2, null=True, blank=True)
    amount_usd = models.DecimalField("Fixed amount (USD)", max_digits=10, decimal_places=2, null=True, blank=True)
    min_order_bdt = models.DecimalField("Minimum order (BDT)", max_digits=12, decimal_places=2, null=True, blank=True)
    min_order_usd = models.DecimalField("Minimum order (USD)", max_digits=10, decimal_places=2, null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Total uses for everyone. Empty = no limit.")
    max_uses_per_customer = models.PositiveIntegerField(null=True, blank=True, default=1,
                                                        help_text="Empty = no limit.")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.discount_type == self.PERCENT and not self.percent:
            raise ValidationError({"percent": "Enter the percentage."})
        if self.discount_type == self.FIXED and self.amount_bdt is None and self.amount_usd is None:
            raise ValidationError("Enter a fixed amount for at least one currency.")

    @property
    def label(self):
        if self.discount_type == self.PERCENT:
            return f"{self.percent.normalize():f}% off"
        parts = [format_price(self.amount_bdt, "bdt"), format_price(self.amount_usd, "usd")]
        return " / ".join(p for p in parts if p) + " off"


class Order(models.Model):
    DRAFT = "draft"
    PENDING_PAYMENT = "pending_payment"
    PAYMENT_PROCESSING = "payment_processing"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (PENDING_PAYMENT, "Pending Payment"),
        (PAYMENT_PROCESSING, "Payment Processing"),
        (PAID, "Paid"),
        (FAILED, "Failed"),
        (CANCELLED, "Cancelled"),
        (REFUNDED, "Refunded"),
        (IN_PROGRESS, "In Progress"),
        (COMPLETED, "Completed"),
    ]
    # Orders in these states can still be paid
    PAYABLE = {DRAFT, PENDING_PAYMENT, FAILED}
    # Orders in these states count as a coupon use
    COUPON_USED = {PAYMENT_PROCESSING, PAID, IN_PROGRESS, COMPLETED}

    number = models.CharField(max_length=20, unique=True, default=new_order_number, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="orders", on_delete=models.PROTECT)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT, db_index=True)

    # Contact details as given at checkout (kept even if the profile changes later)
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    company = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=60, blank=True)
    notes = models.TextField("Project notes", blank=True)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"),
                              help_text="Only if tax applies. No tax rate is set by default.")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    payment_method = models.CharField(max_length=30, blank=True)
    coupon = models.ForeignKey(Coupon, related_name="orders", on_delete=models.SET_NULL, null=True, blank=True)
    coupon_code = models.CharField(max_length=30, blank=True, help_text="Code as applied (kept if the coupon is deleted).")
    quote = models.ForeignKey("service.QuoteRequest", related_name="orders", on_delete=models.SET_NULL,
                              null=True, blank=True)
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.number

    def get_absolute_url(self):
        return reverse("orders:detail", kwargs={"number": self.number})

    @property
    def currency_code(self):
        return CURRENCIES[self.currency]["code"]

    @property
    def is_payable(self):
        return self.status in self.PAYABLE and self.total > 0

    def money(self, value):
        return format_price(value, self.currency)

    @property
    def display_total(self):
        return self.money(self.total)

    @property
    def display_subtotal(self):
        return self.money(self.subtotal)

    @property
    def display_discount(self):
        return self.money(self.discount)

    @property
    def display_tax(self):
        return self.money(self.tax)

    @property
    def has_monthly_items(self):
        return any(item.billing_type == "monthly" for item in self.items.all())

    def recalculate(self, save=True):
        self.subtotal = sum((item.line_total for item in self.items.all()), Decimal("0"))
        self.total = max(self.subtotal - self.discount + self.tax, Decimal("0"))
        if save:
            self.save(update_fields=["subtotal", "total", "updated_at"])


class OrderItem(models.Model):
    """One line of an order. Name and price are copied at checkout so later edits never change old orders."""

    PACKAGE = "package"
    ADDON = "addon"
    QUOTE = "quote"
    KIND_CHOICES = [(PACKAGE, "Package"), (ADDON, "Add-on"), (QUOTE, "Custom quote")]

    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    package = models.ForeignKey("service.Package", on_delete=models.SET_NULL, null=True, blank=True)
    addon = models.ForeignKey("service.AddOn", on_delete=models.SET_NULL, null=True, blank=True)
    service_name = models.CharField(max_length=150, blank=True)
    name = models.CharField(max_length=150)
    billing_type = models.CharField(max_length=10, default="one_time")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    regular_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def display_line_total(self):
        return self.order.money(self.line_total)


def next_invoice_number():
    year = timezone.now().year
    prefix = f"INV-{year}-"
    last = Invoice.objects.filter(number__startswith=prefix).order_by("-number").values_list("number", flat=True).first()
    count = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{count:04d}"


class Invoice(models.Model):
    UNPAID = "unpaid"
    PAID = "paid"
    VOID = "void"
    STATUS_CHOICES = [(UNPAID, "Unpaid"), (PAID, "Paid"), (VOID, "Void")]

    order = models.OneToOneField(Order, related_name="invoice", on_delete=models.CASCADE)
    number = models.CharField(max_length=20, unique=True, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=UNPAID)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()

    class Meta:
        ordering = ["-issue_date", "-id"]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_invoice_number()
        if not self.due_date:
            self.due_date = self.issue_date + timedelta(days=settings.INVOICE_DUE_DAYS)
        super().save(*args, **kwargs)

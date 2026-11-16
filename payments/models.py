import secrets

from django.db import models

from orders.models import CURRENCY_CHOICES
from service.models import format_price


class PaymentBrand(models.Model):
    """A logo shown in "We accept" (Visa, bKash...). Only brands of enabled methods are shown."""

    INTERNATIONAL = "international"
    BANGLADESH = "bangladesh"
    MARKET_CHOICES = [(INTERNATIONAL, "International"), (BANGLADESH, "Bangladesh")]

    code = models.SlugField(max_length=30, unique=True)
    name = models.CharField(max_length=50)
    market = models.CharField(max_length=20, choices=MARKET_CHOICES, default=INTERNATIONAL)
    logo = models.ImageField(upload_to="payments/brands/", blank=True,
                             help_text="Official logo (PNG or SVG-like PNG, transparent background). "
                                       "Without a logo the icon or name is shown.")
    icon = models.CharField(max_length=60, blank=True, help_text='Font Awesome fallback, e.g. "fa-brands fa-cc-visa".')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Payment brand / logo"
        verbose_name_plural = "Payment brands / logos"

    def __str__(self):
        return self.name


class PaymentMethodConfig(models.Model):
    """Which payment methods customers can choose, and the texts they see.

    No secrets live here: API credentials are read only from environment variables.
    """

    code = models.CharField(max_length=30, unique=True, editable=False)
    display_name = models.CharField(max_length=80)
    is_enabled = models.BooleanField(default=False)
    currencies = models.CharField(max_length=20, default="bdt,usd", help_text='Comma separated: "bdt", "usd" or both.')
    description = models.CharField(max_length=200, blank=True, help_text="Short line shown at checkout.")
    instructions = models.TextField(blank=True, help_text="For manual methods: bank details or how to pay. Shown after ordering.")
    brands = models.ManyToManyField(PaymentBrand, blank=True, related_name="methods",
                                    help_text="Logos shown for this method at checkout and in \"We accept\".")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Payment method"

    def __str__(self):
        return self.display_name

    def supports(self, currency):
        return currency in [c.strip() for c in self.currencies.split(",")]


def new_reference():
    return "PAY-" + secrets.token_hex(8).upper()


class Payment(models.Model):
    """One attempt to pay an order through one provider."""

    INITIATED = "initiated"
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    STATUS_CHOICES = [
        (INITIATED, "Initiated"), (PENDING, "Pending"), (SUCCEEDED, "Succeeded"),
        (FAILED, "Failed"), (CANCELLED, "Cancelled"), (REFUNDED, "Refunded"),
    ]
    OPEN = {INITIATED, PENDING}

    order = models.ForeignKey("orders.Order", related_name="payments", on_delete=models.PROTECT)
    provider = models.CharField(max_length=30)
    is_sandbox = models.BooleanField(default=True)
    reference = models.CharField(max_length=40, unique=True, default=new_reference, editable=False,
                                 help_text="Our transaction id sent to the provider.")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=INITIATED, db_index=True)
    provider_transaction_id = models.CharField(max_length=100, blank=True, db_index=True)
    provider_session = models.CharField(max_length=200, blank=True)
    raw_response = models.JSONField(default=dict, blank=True, help_text="Provider data, without any card details.")
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # An order can never have two successful payments (no double charge)
            models.UniqueConstraint(fields=["order"], condition=models.Q(status="succeeded"),
                                    name="one_successful_payment_per_order"),
        ]

    def __str__(self):
        return self.reference

    @property
    def display_amount(self):
        return format_price(self.amount, self.currency)


class PaymentEvent(models.Model):
    """Every callback / webhook received. The unique key makes repeated deliveries harmless."""

    provider = models.CharField(max_length=30)
    event_id = models.CharField(max_length=150)
    payment = models.ForeignKey(Payment, related_name="events", on_delete=models.SET_NULL, null=True, blank=True)
    payload = models.JSONField(default=dict)
    signature_valid = models.BooleanField(default=False)
    result = models.CharField(max_length=255, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        constraints = [models.UniqueConstraint(fields=["provider", "event_id"], name="unique_provider_event")]

    def __str__(self):
        return f"{self.provider}:{self.event_id}"


class Refund(models.Model):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STATUS_CHOICES = [(PENDING, "Pending"), (SUCCEEDED, "Succeeded"), (FAILED, "Failed")]

    payment = models.ForeignKey(Payment, related_name="refunds", on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    provider_refund_id = models.CharField(max_length=100, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Refund {self.payment.reference} ({self.status})"

    @property
    def display_amount(self):
        return format_price(self.amount, self.payment.currency)

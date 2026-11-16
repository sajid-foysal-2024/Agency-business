from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from core.models import OrderedModel, unique_slug

CURRENCIES = {
    "bdt": {"code": "BDT", "symbol": "৳"},
    "usd": {"code": "USD", "symbol": "$"},
}


def format_price(value, currency):
    """'৳ 15,000' / '$ 149.99'. Returns '' when the price is missing."""
    if value is None:
        return ""
    value = Decimal(value)
    pattern = "{:,.0f}" if value == value.to_integral_value() else "{:,.2f}"
    return f"{CURRENCIES[currency]['symbol']} {pattern.format(value)}"


class ServiceCategory(OrderedModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)

    class Meta(OrderedModel.Meta):
        verbose_name = "Service category"
        verbose_name_plural = "Service categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, ServiceCategory.objects.all(), fallback="category")
        super().save(*args, **kwargs)


class ServiceQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class Service(OrderedModel):
    """A service the agency sells (e.g. Web Development). Shown on the home page and its own page."""

    category = models.ForeignKey(ServiceCategory, related_name="services", on_delete=models.SET_NULL,
                                 null=True, blank=True)
    title = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True,
                            help_text="Used in the URL: /services/<slug>/. Filled in from the title.")
    icon = models.CharField(max_length=60, blank=True, default="fa-solid fa-layer-group",
                            help_text='Font Awesome class, e.g. "fa-solid fa-code".')
    description = models.TextField(help_text="Short text shown on the home page and service cards.")
    image = models.ImageField(upload_to="services/", blank=True)
    button_text = models.CharField(max_length=50, blank=True, default="Read More",
                                   help_text="Home page button. Leave blank to hide it.")

    # Details page
    hero_subtitle = models.CharField(max_length=150, blank=True, help_text="Small line above the title.")
    hero_image = models.ImageField(upload_to="services/hero/", blank=True,
                                   help_text="Wide background image. Uses the main image when empty.")
    overview_title = models.CharField(max_length=150, blank=True, default="Service Overview")
    overview = models.TextField(blank=True, help_text="Leave an empty line between paragraphs.")
    offerings_title = models.CharField(max_length=150, blank=True, default="What We Offer")
    deliverables = models.TextField(blank=True, help_text="One deliverable per line. Shown on the service page.")
    delivery_time = models.CharField(max_length=60, blank=True, help_text='Typical delivery, e.g. "7-14 days"')
    allow_custom_quote = models.BooleanField(default=True, help_text='Show a "Request a Custom Quote" button.')

    # SEO
    meta_title = models.CharField(max_length=100, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)

    objects = ServiceQuerySet.as_manager()

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title, Service.objects.all(), fallback="service")
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("services:detail", kwargs={"slug": self.slug})

    @property
    def deliverable_list(self):
        return [line.strip() for line in self.deliverables.splitlines() if line.strip()]

    @property
    def hero_background_url(self):
        """Hero image, else the main image, else '' (the template then uses a default)."""
        image = self.hero_image or self.image
        return image.url if image else ""

    @property
    def overview_paragraphs(self):
        return [p.strip() for p in self.overview.split("\n\n") if p.strip()]


class ServiceOffering(models.Model):
    """One card in a service's "What We Offer" section."""

    service = models.ForeignKey(Service, related_name="offerings", on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=60, blank=True, default="fa-solid fa-check",
                            help_text='Font Awesome class, e.g. "fa-solid fa-film".')
    order = models.PositiveIntegerField(default=0)
    is_demo = models.BooleanField("Demo data", default=False, editable=False,
                                  help_text="Created by the demo_packages command. Safe to delete.")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Offering"

    def __str__(self):
        return self.title


class PackageQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def single(self):
        return self.filter(package_type=Package.SINGLE)

    def combo(self):
        return self.filter(package_type=Package.COMBO)


class Package(OrderedModel):
    """A price plan. Single = one service. Combo = several services together."""

    SINGLE = "single"
    COMBO = "combo"
    TYPE_CHOICES = [(SINGLE, "Single service package"), (COMBO, "Combo package")]

    ONE_TIME = "one_time"
    MONTHLY = "monthly"
    BILLING_CHOICES = [(ONE_TIME, "One-time project"), (MONTHLY, "Monthly plan")]

    package_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=SINGLE)
    billing_type = models.CharField(max_length=10, choices=BILLING_CHOICES, default=ONE_TIME,
                                    help_text="Monthly plans are billed one month per order (no auto-renewal).")
    service = models.ForeignKey(Service, related_name="packages", on_delete=models.CASCADE,
                                null=True, blank=True,
                                help_text="Required for single packages. Leave empty for combos.")
    included_services = models.ManyToManyField(
        Service, related_name="combo_packages", blank=True,
        help_text="Combo packages only: pick 2 or more services. The combo shows on each of their pages.",
    )
    name = models.CharField(max_length=100, help_text='e.g. "Basic", "Business Website", "Startup Combo"')
    tagline = models.CharField(max_length=200, blank=True, help_text="One short line under the name.")

    # Prices: each currency is independent. Leave blank = "Price on request".
    price_bdt = models.DecimalField("Price (BDT)", max_digits=12, decimal_places=2, null=True, blank=True)
    price_usd = models.DecimalField("Price (USD)", max_digits=10, decimal_places=2, null=True, blank=True)
    regular_price_bdt = models.DecimalField("Regular price (BDT)", max_digits=12, decimal_places=2,
                                            null=True, blank=True, help_text="Optional. Shown crossed out.")
    regular_price_usd = models.DecimalField("Regular price (USD)", max_digits=10, decimal_places=2,
                                            null=True, blank=True, help_text="Optional. Shown crossed out.")
    price_note = models.CharField(max_length=40, blank=True, help_text='e.g. "one-time", "/ month"')
    discount_text = models.CharField(max_length=60, blank=True, help_text='e.g. "Save 15%"')
    delivery_time = models.CharField(max_length=60, blank=True, help_text='e.g. "7 days delivery"')

    is_popular = models.BooleanField(default=False, help_text='Shows a "Popular" badge.')
    is_featured = models.BooleanField(default=False, help_text="Also show on the main Services page.")
    button_text = models.CharField(max_length=40, blank=True, default="Order Now")
    is_demo = models.BooleanField("Demo data", default=False, editable=False,
                                  help_text="Created by the demo_packages command. Safe to delete.")

    objects = PackageQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        pass

    def __str__(self):
        if self.package_type == self.SINGLE and self.service_id:
            return f"{self.service} - {self.name}"
        return f"{self.name} (combo)"

    def clean(self):
        if self.package_type == self.SINGLE and not self.service_id:
            raise ValidationError({"service": "A single service package needs a service."})
        if self.package_type == self.COMBO and self.service_id:
            raise ValidationError({"service": "Leave this empty for combos. Use \"Included services\" instead."})

    @property
    def is_combo(self):
        return self.package_type == self.COMBO

    @property
    def is_monthly(self):
        return self.billing_type == self.MONTHLY

    def can_checkout(self, currency):
        """Online checkout needs an active package with a price in that currency."""
        return self.is_active and currency in CURRENCIES and self.price(currency) is not None

    def price(self, currency):
        return getattr(self, f"price_{currency}")

    def display_price(self, currency):
        return format_price(self.price(currency), currency)

    @property
    def display_bdt(self):
        return format_price(self.price_bdt, "bdt")

    @property
    def display_usd(self):
        return format_price(self.price_usd, "usd")

    @property
    def display_regular_bdt(self):
        return format_price(self.regular_price_bdt, "bdt")

    @property
    def display_regular_usd(self):
        return format_price(self.regular_price_usd, "usd")


class PackageFeature(models.Model):
    package = models.ForeignKey(Package, related_name="features", on_delete=models.CASCADE)
    text = models.CharField(max_length=200)
    is_included = models.BooleanField(default=True, help_text="Uncheck to show it as not included.")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Feature"

    def __str__(self):
        return self.text


class FAQ(OrderedModel):
    service = models.ForeignKey(Service, related_name="faqs", on_delete=models.CASCADE,
                                null=True, blank=True,
                                help_text="Leave empty to show this question on every service page.")
    question = models.CharField(max_length=255)
    answer = models.TextField()
    is_demo = models.BooleanField("Demo data", default=False, editable=False,
                                  help_text="Created by the demo_packages command. Safe to delete.")

    class Meta(OrderedModel.Meta):
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question


class AddOnQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def for_service(self, service):
        """Add-ons for this service plus the ones offered with every service."""
        return self.active().filter(models.Q(service=service) | models.Q(service__isnull=True))


class AddOn(OrderedModel):
    """An optional extra a customer can add at checkout (rush delivery, extra revisions...)."""

    service = models.ForeignKey(Service, related_name="addons", on_delete=models.CASCADE, null=True, blank=True,
                                help_text="Leave empty to offer this add-on with every service.")
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=200, blank=True)
    price_bdt = models.DecimalField("Price (BDT)", max_digits=12, decimal_places=2, null=True, blank=True)
    price_usd = models.DecimalField("Price (USD)", max_digits=10, decimal_places=2, null=True, blank=True)
    is_demo = models.BooleanField("Demo data", default=False, editable=False,
                                  help_text="Created by the demo_packages command. Safe to delete.")

    objects = AddOnQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Add-on"

    def __str__(self):
        return self.name

    def price(self, currency):
        return getattr(self, f"price_{currency}")

    def display_price(self, currency):
        return format_price(self.price(currency), currency)

    @property
    def display_bdt(self):
        return format_price(self.price_bdt, "bdt")

    @property
    def display_usd(self):
        return format_price(self.price_usd, "usd")


class QuoteRequest(models.Model):
    """A custom project brief. Staff reply with a quote (and can turn it into an order)."""

    STATUS_NEW = "new"
    STATUS_QUOTED = "quoted"
    STATUS_ACCEPTED = "accepted"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [(STATUS_NEW, "New"), (STATUS_QUOTED, "Quoted"), (STATUS_ACCEPTED, "Accepted"),
                      (STATUS_CLOSED, "Closed")]

    user = models.ForeignKey("auth.User", related_name="quote_requests", on_delete=models.SET_NULL,
                             null=True, blank=True)
    service = models.ForeignKey(Service, related_name="quote_requests", on_delete=models.SET_NULL,
                                null=True, blank=True)
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    currency = models.CharField(max_length=3, choices=[("bdt", "BDT"), ("usd", "USD")], default="usd")
    budget = models.CharField(max_length=60, blank=True, help_text="As written by the customer.")
    brief = models.TextField()

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_NEW)
    quoted_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                        help_text="Your quote, in the currency above.")
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Quote: {self.full_name} ({self.service or 'custom'})"


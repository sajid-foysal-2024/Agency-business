from django.db import models

from core.models import OrderedModel, SingletonModel, build_social_links


# ---------------------------------------------------------------------------
# Global site settings (used on every page)
# ---------------------------------------------------------------------------

class SiteSetting(SingletonModel):
    # Branding
    brand_name = models.CharField(max_length=100, default="OS Agency")
    tagline = models.CharField(max_length=200, blank=True)
    brand_icon = models.CharField(
        max_length=60, default="fa-regular fa-face-smile", blank=True,
        help_text='Font Awesome class shown before the brand name, e.g. "fa-solid fa-bolt". '
                  "Ignored when a logo is uploaded.",
    )
    logo = models.ImageField(upload_to="site/", blank=True)
    favicon = models.ImageField(upload_to="site/", blank=True)
    founded_year = models.PositiveSmallIntegerField(null=True, blank=True,
                                                    help_text='Used for the "Years Experience" counter.')
    about_short = models.TextField("Short about text", blank=True, help_text="Shown in the footer.")

    # Header button (top right)
    header_button_text = models.CharField(max_length=40, blank=True, default="Let's Talk",
                                          help_text="Leave blank to hide the button.")
    header_button_link = models.CharField(max_length=200, blank=True, default="/#cta")

    # SEO
    meta_description = models.CharField(max_length=300, blank=True)
    meta_keywords = models.CharField(max_length=300, blank=True)

    # Contact
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)

    # Social links (left blank = hidden)
    facebook_url = models.URLField(blank=True)
    x_url = models.URLField("X (Twitter) URL", blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)

    # Footer
    copyright_name = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Site setting"
        verbose_name_plural = "Site settings"

    def __str__(self):
        return self.brand_name

    @property
    def social_links(self):
        """Only the social links that are filled in, ready for templates."""
        return build_social_links(self, ["facebook_url", "x_url", "instagram_url", "linkedin_url", "youtube_url"])


# ---------------------------------------------------------------------------
# Home page content
# ---------------------------------------------------------------------------

class HomePage(SingletonModel):
    """Section headings and texts for the home page."""

    meta_title = models.CharField(max_length=100, blank=True, help_text="Browser tab title. Defaults to the brand name.")

    services_subtitle = models.CharField(max_length=100, default="Services")
    services_title = models.CharField(max_length=150, default="How We Help You")

    show_stats = models.BooleanField("Show counters", default=True)

    features_subtitle = models.CharField(max_length=100, default="Why Choose Us")
    features_title = models.CharField(max_length=150, default="What Makes Us Different")
    features_text = models.TextField(blank=True)

    works_subtitle = models.CharField(max_length=100, default="Portfolio")
    works_title = models.CharField(max_length=150, default="Our Recent Works")
    works_limit = models.PositiveSmallIntegerField(default=6, help_text="How many featured projects to show.")

    process_subtitle = models.CharField(max_length=100, default="Process")
    process_title = models.CharField(max_length=150, default="How We Work")

    clients_subtitle = models.CharField(max_length=100, default="Clients")
    clients_title = models.CharField(max_length=150, default="Trusted By")

    show_cta = models.BooleanField("Show call-to-action banner", default=True)
    cta_title = models.CharField(max_length=150, default="Have a project in mind?")
    cta_text = models.TextField(blank=True, default="Tell us about your idea and we will help you build it.")
    cta_button_text = models.CharField(max_length=50, blank=True, default="Start a Project")
    cta_button_link = models.CharField(max_length=200, blank=True, default="#newsletter")

    team_subtitle = models.CharField(max_length=100, default="Team")
    team_title = models.CharField(max_length=150, default="Meet Our Experts")
    team_button_text = models.CharField(max_length=50, default="View All Developers", blank=True)

    testimonials_subtitle = models.CharField(max_length=100, default="Testimonial")
    testimonials_title = models.CharField(max_length=150, default="Our Clients Say")

    show_newsletter = models.BooleanField(default=True)
    newsletter_subtitle = models.CharField(max_length=100, default="Newsletter")
    newsletter_title = models.CharField(max_length=150, default="Stay In Touch")
    newsletter_text = models.TextField(blank=True, default="Subscribe to get our latest news and offers.")
    newsletter_button_text = models.CharField(max_length=30, default="Subscribe")

    class Meta:
        verbose_name = "Home page"
        verbose_name_plural = "Home page"

    def __str__(self):
        return "Home page content"


class HeroSlide(OrderedModel):
    image = models.ImageField(upload_to="slides/")
    subtitle = models.CharField(max_length=100, default="Welcome")
    title = models.CharField(max_length=100)
    text = models.TextField(blank=True)
    button_text = models.CharField(max_length=50, default="Explore More", blank=True)
    button_link = models.CharField(max_length=200, blank=True, help_text='A URL or a section link like "#about".')
    second_button_text = models.CharField(max_length=50, blank=True, default="Our Services")
    second_button_link = models.CharField(max_length=200, blank=True, default="#services")

    class Meta(OrderedModel.Meta):
        verbose_name = "Hero slide"

    def __str__(self):
        return self.title


class About(SingletonModel):
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide the About section.")
    subtitle = models.CharField(max_length=100, default="About Us")
    title = models.CharField(max_length=150, default="Who We Are")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="about/", blank=True)
    primary_button_text = models.CharField(max_length=50, blank=True, default="Contact Us")
    primary_button_link = models.CharField(max_length=200, blank=True, default="#newsletter")
    secondary_button_text = models.CharField(max_length=50, blank=True, default="Our Services")
    secondary_button_link = models.CharField(max_length=200, blank=True, default="#services")

    class Meta:
        verbose_name = "About section"
        verbose_name_plural = "About section"

    def __str__(self):
        return self.title


class AboutPoint(models.Model):
    about = models.ForeignKey(About, related_name="points", on_delete=models.CASCADE)
    text = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text


class Service(OrderedModel):
    title = models.CharField(max_length=100)
    description = models.TextField()
    image = models.ImageField(upload_to="services/", blank=True)
    button_text = models.CharField(max_length=50, blank=True, default="Read More")
    button_link = models.CharField(max_length=200, blank=True, help_text="Leave blank to hide the button.")

    def __str__(self):
        return self.title


class Stat(OrderedModel):
    """One counter in the stats bar. Numbers can be counted automatically from the database."""

    SOURCE_MANUAL = "manual"
    SOURCE_YEARS = "years"
    SOURCE_PROJECTS = "projects"
    SOURCE_DEVELOPERS = "developers"
    SOURCE_CLIENTS = "clients"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Type the number myself"),
        (SOURCE_YEARS, "Auto: years since founded (Site settings)"),
        (SOURCE_PROJECTS, "Auto: number of projects"),
        (SOURCE_DEVELOPERS, "Auto: number of developers"),
        (SOURCE_CLIENTS, "Auto: number of client reviews + testimonials"),
    ]

    label = models.CharField(max_length=60)
    icon = models.CharField(max_length=60, blank=True, default="fa-solid fa-star",
                            help_text='Font Awesome class, e.g. "fa-solid fa-briefcase".')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    value = models.PositiveIntegerField(default=0, help_text='Only used when source is "Type the number myself".')
    suffix = models.CharField(max_length=5, blank=True, default="+", help_text='e.g. "+" or "%"')

    def __str__(self):
        return self.label


class Feature(OrderedModel):
    """A "Why choose us" card."""

    title = models.CharField(max_length=100)
    text = models.TextField(blank=True)
    icon = models.CharField(max_length=60, blank=True, default="fa-solid fa-check",
                            help_text='Font Awesome class, e.g. "fa-solid fa-rocket".')

    def __str__(self):
        return self.title


class ProcessStep(OrderedModel):
    """One step of "How we work". Steps are numbered by their order."""

    title = models.CharField(max_length=100)
    text = models.TextField(blank=True)
    icon = models.CharField(max_length=60, blank=True, default="fa-solid fa-circle",
                            help_text='Font Awesome class, e.g. "fa-solid fa-comments".')

    class Meta(OrderedModel.Meta):
        verbose_name = "Process step"

    def __str__(self):
        return self.title


class ClientLogo(OrderedModel):
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to="clients/")
    website = models.URLField(blank=True)

    class Meta(OrderedModel.Meta):
        verbose_name = "Client logo"

    def __str__(self):
        return self.name


class Testimonial(OrderedModel):
    name = models.CharField(max_length=100)
    profession = models.CharField(max_length=100, blank=True)
    message = models.TextField()
    photo = models.ImageField(upload_to="testimonials/", blank=True)

    def __str__(self):
        return self.name


class Subscriber(models.Model):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

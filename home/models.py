from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# Reusable base models
# ---------------------------------------------------------------------------

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OrderedModel(TimeStampedModel):
    """List items that admins can sort and hide without deleting."""

    order = models.PositiveIntegerField(default=0, help_text="Lower numbers show first.")
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide from the website.")

    class Meta:
        abstract = True
        ordering = ["order", "id"]


class SingletonModel(models.Model):
    """A model that only ever has one row (pk=1), edited from the admin."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # The single settings row should never be removed.
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


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
        links = [
            ("Facebook", "fa-brands fa-facebook-f", self.facebook_url),
            ("X", "fa-brands fa-x-twitter", self.x_url),
            ("Instagram", "fa-brands fa-instagram", self.instagram_url),
            ("LinkedIn", "fa-brands fa-linkedin-in", self.linkedin_url),
            ("YouTube", "fa-brands fa-youtube", self.youtube_url),
        ]
        return [{"name": n, "icon": i, "url": u} for n, i, u in links if u]


# ---------------------------------------------------------------------------
# Home page content
# ---------------------------------------------------------------------------

class HomePage(SingletonModel):
    """Section headings and texts for the home page."""

    meta_title = models.CharField(max_length=100, blank=True, help_text="Browser tab title. Defaults to the brand name.")

    services_subtitle = models.CharField(max_length=100, default="Services")
    services_title = models.CharField(max_length=150, default="How We Help You")

    team_subtitle = models.CharField(max_length=100, default="Team")
    team_title = models.CharField(max_length=150, default="Meet Our Experts")

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


class TeamMember(OrderedModel):
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=100, blank=True, help_text='e.g. "Web Developer"')
    photo = models.ImageField(upload_to="team/")
    bio = models.TextField(blank=True)
    facebook_url = models.URLField(blank=True)
    x_url = models.URLField("X (Twitter) URL", blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)

    class Meta(OrderedModel.Meta):
        verbose_name = "Team member"

    def __str__(self):
        return self.name

    @property
    def social_links(self):
        links = [
            ("Facebook", "fa-brands fa-facebook-f", self.facebook_url),
            ("X", "fa-brands fa-x-twitter", self.x_url),
            ("Instagram", "fa-brands fa-instagram", self.instagram_url),
            ("LinkedIn", "fa-brands fa-linkedin-in", self.linkedin_url),
        ]
        return [{"name": n, "icon": i, "url": u} for n, i, u in links if u]


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

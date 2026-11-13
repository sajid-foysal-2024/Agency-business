from django.core.validators import FileExtensionValidator, MaxValueValidator
from django.db import models
from django.urls import reverse

from core.models import OrderedModel, build_social_links, unique_slug

DEVELOPER_SOCIAL_FIELDS = [
    "github_url", "linkedin_url", "facebook_url", "x_url",
    "instagram_url", "behance_url", "dribbble_url", "website_url",
]


class DeveloperQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def on_home_page(self):
        return self.active().filter(show_on_home=True)


class Developer(OrderedModel):
    """One developer (employee). Everything on their portfolio page comes from here."""

    # Basic info
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True,
                            help_text="Used in the portfolio URL. Filled in automatically from the name.")
    designation = models.CharField(max_length=100, blank=True, help_text='e.g. "Full Stack Developer"')
    photo = models.ImageField(upload_to="developers/photos/", blank=True,
                              help_text="A cut-out photo (transparent PNG) looks best on the portfolio hero.")

    # Portfolio texts
    short_description = models.TextField(
        max_length=400, blank=True,
        help_text="2-3 sentences about skills, expertise and responsibilities. "
                  "Shown on the team page. Falls back to the headline / bio when empty.",
    )
    headline = models.CharField(max_length=255, blank=True,
                                help_text="Big intro line in the About part, e.g. \"I'm a developer based in Dhaka who loves clean code.\"")
    bio = models.TextField(blank=True, help_text="About text. Leave an empty line between paragraphs.")
    cv = models.FileField(upload_to="developers/cv/", blank=True,
                          validators=[FileExtensionValidator(["pdf", "doc", "docx"])])

    # Work info
    experience_years = models.PositiveSmallIntegerField(default=0)
    joined_on = models.DateField(null=True, blank=True)
    is_available = models.BooleanField("Available for new projects", default=True)
    show_on_home = models.BooleanField("Show on home page", default=True,
                                       help_text="Show this developer in the home page Team section.")

    # Contact
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    location = models.CharField(max_length=100, blank=True)

    # Social links (blank = hidden)
    github_url = models.URLField("GitHub URL", blank=True)
    linkedin_url = models.URLField("LinkedIn URL", blank=True)
    facebook_url = models.URLField("Facebook URL", blank=True)
    x_url = models.URLField("X (Twitter) URL", blank=True)
    instagram_url = models.URLField("Instagram URL", blank=True)
    behance_url = models.URLField("Behance URL", blank=True)
    dribbble_url = models.URLField("Dribbble URL", blank=True)
    website_url = models.URLField("Website URL", blank=True)

    # "Let's Talk" area at the bottom of the portfolio
    cta_title = models.CharField("Call-to-action title", max_length=150, blank=True,
                                 default="Do you have any project?")
    cta_text = models.TextField("Call-to-action text", blank=True)

    objects = DeveloperQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Developer"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, Developer.objects.all(), fallback="developer")
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("developers:detail", kwargs={"slug": self.slug})

    @property
    def first_name(self):
        return self.name.split()[0] if self.name else ""

    @property
    def initials(self):
        return "".join(part[0] for part in self.name.split()[:2]).upper()

    @property
    def social_links(self):
        return build_social_links(self, DEVELOPER_SOCIAL_FIELDS)

    @property
    def team_summary(self):
        """Text for the team page: short description, else headline, else the start of the bio."""
        return self.short_description or self.headline or self.bio

    @property
    def bio_paragraphs(self):
        return [p.strip() for p in self.bio.split("\n\n") if p.strip()]


class Skill(models.Model):
    developer = models.ForeignKey(Developer, related_name="skills", on_delete=models.CASCADE)
    name = models.CharField(max_length=60)
    percentage = models.PositiveSmallIntegerField(default=80, validators=[MaxValueValidator(100)],
                                                  help_text="0 to 100")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.name} ({self.percentage}%)"


class DeveloperService(models.Model):
    """Services one developer offers ("My Services" on their portfolio)."""

    developer = models.ForeignKey(Developer, related_name="services", on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=60, blank=True, default="fa-solid fa-code",
                            help_text='Font Awesome class, e.g. "fa-solid fa-mobile-screen".')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Service"

    def __str__(self):
        return self.title


class ProjectQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class Project(OrderedModel):
    """A piece of work shown in a developer's "My Works" gallery."""

    developer = models.ForeignKey(Developer, related_name="projects", on_delete=models.CASCADE)
    title = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, blank=True)
    category = models.CharField(max_length=60, blank=True, help_text='e.g. "Mobile App", "Website"')
    image = models.ImageField(upload_to="developers/projects/", blank=True)
    summary = models.CharField(max_length=255, blank=True, help_text="One line shown on the details page header.")
    description = models.TextField(blank=True)
    client = models.CharField(max_length=100, blank=True)
    technologies = models.CharField(max_length=255, blank=True, help_text="Comma separated, e.g. Django, React")
    completed_on = models.DateField(null=True, blank=True)
    live_url = models.URLField("Live URL", blank=True)
    source_url = models.URLField("Source code URL", blank=True)
    is_featured = models.BooleanField(default=True, help_text="Featured works show first on the portfolio.")

    objects = ProjectQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        ordering = ["-is_featured", "order", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["developer", "slug"], name="unique_project_slug_per_developer"),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title, Project.objects.filter(developer_id=self.developer_id),
                                    fallback="project")
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("developers:project", kwargs={"slug": self.developer.slug, "project_slug": self.slug})

    @property
    def technology_list(self):
        return [t.strip() for t in self.technologies.split(",") if t.strip()]


class ClientReview(models.Model):
    """What clients say about one developer."""

    developer = models.ForeignKey(Developer, related_name="reviews", on_delete=models.CASCADE)
    client_name = models.CharField(max_length=100)
    client_role = models.CharField(max_length=100, blank=True, help_text='e.g. "Business Owner"')
    message = models.TextField()
    photo = models.ImageField(upload_to="developers/reviews/", blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.client_name} on {self.developer}"

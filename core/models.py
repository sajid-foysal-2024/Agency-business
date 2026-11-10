"""Abstract base models shared by all apps. They create no tables themselves."""
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


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


def unique_slug(instance, value, queryset, fallback="item", max_length=120):
    """Return a slug for `value` that is unique within `queryset`."""
    base = slugify(value)[:max_length] or fallback
    slug, n = base, 2
    queryset = queryset.exclude(pk=instance.pk) if instance.pk else queryset
    while queryset.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


SOCIAL_ICONS = {
    "facebook_url": ("Facebook", "fa-brands fa-facebook-f"),
    "x_url": ("X", "fa-brands fa-x-twitter"),
    "instagram_url": ("Instagram", "fa-brands fa-instagram"),
    "linkedin_url": ("LinkedIn", "fa-brands fa-linkedin-in"),
    "youtube_url": ("YouTube", "fa-brands fa-youtube"),
    "github_url": ("GitHub", "fa-brands fa-github"),
    "behance_url": ("Behance", "fa-brands fa-behance"),
    "dribbble_url": ("Dribbble", "fa-brands fa-dribbble"),
    "website_url": ("Website", "fa-solid fa-globe"),
}


def build_social_links(obj, fields):
    """Turn filled-in URL fields into [{name, icon, url}] for templates."""
    links = []
    for field in fields:
        url = getattr(obj, field, "")
        if url:
            name, icon = SOCIAL_ICONS[field]
            links.append({"name": name, "icon": icon, "url": url})
    return links

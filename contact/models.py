from django.db import models


class ContactInquiry(models.Model):
    """A message sent from the Contact Us form."""

    STATUS_PENDING = "pending"
    STATUS_CONTACTED = "contacted"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONTACTED, "Contacted"),
        (STATUS_COMPLETED, "Completed"),
    ]

    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    subject = models.CharField(max_length=150)
    service = models.ForeignKey("service.Service", related_name="inquiries", on_delete=models.SET_NULL,
                                null=True, blank=True, verbose_name="Service interested in")
    message = models.TextField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    admin_note = models.TextField(blank=True, help_text="Private note, only visible in the admin.")
    notification_sent = models.BooleanField(default=False, editable=False,
                                            help_text="Whether the email notification was delivered.")
    created_at = models.DateTimeField("Submitted", auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Contact inquiry"
        verbose_name_plural = "Contact inquiries"

    def __str__(self):
        return f"{self.full_name}: {self.subject}"

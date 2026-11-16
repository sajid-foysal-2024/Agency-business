import re

from django import forms

from service.models import Service

from .models import ContactInquiry

INPUT_CLASS = "form-control contact-input"


class ContactForm(forms.ModelForm):
    # Spam trap: hidden from people, bots fill it in. Any value = rejected.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={
        "tabindex": "-1", "autocomplete": "off", "class": "contact-hp",
    }))

    service = forms.ModelChoiceField(
        queryset=Service.objects.none(),
        required=False,
        empty_label="Select a service (optional)",
        label="Service interested in",
        widget=forms.Select(attrs={"class": "form-select contact-input"}),
    )

    class Meta:
        model = ContactInquiry
        fields = ["full_name", "email", "phone", "subject", "service", "message"]
        labels = {
            "full_name": "Full name",
            "email": "Email address",
            "phone": "Phone number (optional)",
        }
        widgets = {
            "full_name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Your full name",
                                                "autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "you@example.com",
                                             "autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "+880 1XXX-XXXXXX",
                                            "autocomplete": "tel", "inputmode": "tel"}),
            "subject": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "What is this about?"}),
            "message": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 6,
                                             "placeholder": "Tell us about your project..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = Service.objects.active().only("title")

    def full_clean(self):
        """After validation, flag fields with errors for Bootstrap and screen readers."""
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                attrs = self.fields[name].widget.attrs
                attrs["class"] = f"{attrs.get('class', '')} is-invalid".strip()
                attrs["aria-invalid"] = "true"
                attrs["aria-describedby"] = f"id_{name}_error"

    def clean_full_name(self):
        name = self.cleaned_data["full_name"].strip()
        if len(name) < 2:
            raise forms.ValidationError("Please enter your full name.")
        return name

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        if phone and not re.fullmatch(r"\+?[\d\s\-()]{7,20}", phone):
            raise forms.ValidationError("Please enter a valid phone number.")
        return phone

    def clean_subject(self):
        return self.cleaned_data["subject"].strip()

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 10:
            raise forms.ValidationError("Please write a little more (at least 10 characters).")
        return message

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Spam detected.")
        return ""

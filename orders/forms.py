import re

from django import forms

from service.models import AddOn, QuoteRequest, Service

from .models import CURRENCY_CHOICES

INPUT = "form-control contact-input"


def clean_phone_value(phone):
    phone = (phone or "").strip()
    if phone and not re.fullmatch(r"\+?[\d\s\-()]{7,20}", phone):
        raise forms.ValidationError("Please enter a valid phone number.")
    return phone


class CheckoutForm(forms.Form):
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES, widget=forms.RadioSelect)
    addons = forms.ModelMultipleChoiceField(queryset=AddOn.objects.none(), required=False,
                                            widget=forms.CheckboxSelectMultiple, label="Optional add-ons")
    full_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={"class": INPUT, "autocomplete": "name"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": INPUT, "autocomplete": "email"}))
    phone = forms.CharField(max_length=30, required=False,
                            widget=forms.TextInput(attrs={"class": INPUT, "autocomplete": "tel"}))
    company = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={"class": INPUT}))
    country = forms.CharField(max_length=60, required=False,
                              widget=forms.TextInput(attrs={"class": INPUT, "autocomplete": "country-name"}))
    notes = forms.CharField(required=False, label="Project notes (optional)",
                            widget=forms.Textarea(attrs={"class": INPUT, "rows": 4,
                                                         "placeholder": "Links, goals, deadlines..."}))

    def __init__(self, *args, addons_queryset=None, available_currencies=None, **kwargs):
        super().__init__(*args, **kwargs)
        if addons_queryset is not None:
            self.fields["addons"].queryset = addons_queryset
        if available_currencies is not None:
            self.fields["currency"].choices = [c for c in CURRENCY_CHOICES if c[0] in available_currencies]

    def clean_full_name(self):
        name = self.cleaned_data["full_name"].strip()
        if len(name) < 2:
            raise forms.ValidationError("Please enter your full name.")
        return name

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data.get("phone"))


class QuoteRequestForm(forms.ModelForm):
    service = forms.ModelChoiceField(queryset=Service.objects.none(), required=False,
                                     empty_label="Not sure / several services",
                                     widget=forms.Select(attrs={"class": "form-select contact-input"}))

    class Meta:
        model = QuoteRequest
        fields = ["service", "full_name", "email", "phone", "currency", "budget", "brief"]
        labels = {"full_name": "Full name", "currency": "Preferred currency", "budget": "Budget (optional)",
                  "brief": "Project brief"}
        widgets = {
            "full_name": forms.TextInput(attrs={"class": INPUT}),
            "email": forms.EmailInput(attrs={"class": INPUT}),
            "phone": forms.TextInput(attrs={"class": INPUT}),
            "currency": forms.Select(attrs={"class": "form-select contact-input"}),
            "budget": forms.TextInput(attrs={"class": INPUT, "placeholder": "e.g. $2,000 or ৳150,000"}),
            "brief": forms.Textarea(attrs={"class": INPUT, "rows": 6,
                                           "placeholder": "What do you need, by when, and any examples you like"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = Service.objects.active()

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data.get("phone"))

    def clean_brief(self):
        brief = self.cleaned_data["brief"].strip()
        if len(brief) < 20:
            raise forms.ValidationError("Please describe the project in a little more detail.")
        return brief

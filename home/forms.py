from django import forms


class SubscribeForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={
            "class": "form-control border-0 bg-dark rounded-pill w-100 py-4 ps-4 pe-5",
            "placeholder": "Your email",
            "autocomplete": "email",
        }),
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

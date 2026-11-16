from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

INPUT = "form-control contact-input"


class SignupForm(UserCreationForm):
    """Sign up with name + email. The email is also the username."""

    full_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={"class": INPUT, "autocomplete": "name"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": INPUT, "autocomplete": "email"}))

    class Meta:
        model = User
        fields = ("full_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("password1", "password2"):
            self.fields[name].widget.attrs.update({"class": INPUT, "autocomplete": "new-password"})

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Please log in.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        first, _, last = self.cleaned_data["full_name"].strip().partition(" ")
        user.first_name, user.last_name = first[:150], last[:150]
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Email", widget=forms.EmailInput(attrs={"class": INPUT, "autocomplete": "email",
                                                                             "autofocus": True}))
    password = forms.CharField(label="Password", strip=False,
                               widget=forms.PasswordInput(attrs={"class": INPUT, "autocomplete": "current-password"}))

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()

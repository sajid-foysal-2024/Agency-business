from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, resolve_url
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView

from core.ratelimit import rate_limit
from home.models import SiteSetting

from .forms import LoginForm, SignupForm


@method_decorator(rate_limit("login", limit=10, window=60), name="dispatch")
class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Django's LoginView puts its own "site" in the context; keep ours (brand, logo, links)
        context["site"] = SiteSetting.load()
        return context


@method_decorator(rate_limit("signup", limit=5, window=60), name="dispatch")
class SignupView(CreateView):
    template_name = "accounts/signup.html"
    form_class = SignupForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("orders:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "")
        return context

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, {self.request.get_host()},
                                                        require_https=self.request.is_secure()):
            return redirect(next_url)
        return redirect(resolve_url("orders:dashboard"))

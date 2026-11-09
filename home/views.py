from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from .forms import SubscribeForm
from .models import Subscriber
from .selectors import get_home_page_context


class HomeView(TemplateView):
    template_name = "home/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_home_page_context())
        context["subscribe_form"] = SubscribeForm()
        return context


class SubscribeView(View):
    http_method_names = ["post"]

    def post(self, request):
        form = SubscribeForm(request.POST)
        if form.is_valid():
            subscriber, created = Subscriber.objects.get_or_create(email=form.cleaned_data["email"])
            if created:
                messages.success(request, "Thank you for subscribing!")
            elif not subscriber.is_active:
                subscriber.is_active = True
                subscriber.save(update_fields=["is_active"])
                messages.success(request, "Welcome back! Your subscription is active again.")
            else:
                messages.info(request, "You are already subscribed.")
        else:
            messages.error(request, "Please enter a valid email address.")

        return redirect(reverse("home:index") + "#newsletter")

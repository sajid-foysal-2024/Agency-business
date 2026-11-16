from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView

from home.models import SiteSetting
from service.models import Service
from service.whatsapp import whatsapp_url

from .forms import ContactForm
from .services import map_urls, notify_agency, save_inquiry

SESSION_SENT_KEY = "contact_sent"


class ContactView(FormView):
    template_name = "contact/contact.html"
    form_class = ContactForm

    def get_initial(self):
        """/contact/?service=web-development pre-selects that service."""
        initial = super().get_initial()
        slug = self.request.GET.get("service")
        if slug:
            service = Service.objects.active().filter(slug=slug).first()
            if service:
                initial["service"] = service
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site = SiteSetting.load()
        context.update({
            "sent": self.request.session.pop(SESSION_SENT_KEY, False),
            "map": map_urls(site.address),
            "whatsapp_url": whatsapp_url(
                site.whatsapp_number, f"Hello {site.brand_name}!\nI would like to discuss a project."),
            "breadcrumbs": [{"label": "Contact", "url": None}],
        })
        return context

    def form_valid(self, form):
        inquiry, created = save_inquiry(form.cleaned_data)
        if created:
            notify_agency(inquiry, SiteSetting.load(), self.request)
        # Post/Redirect/Get: refreshing the page will not send the form again.
        self.request.session[SESSION_SENT_KEY] = True
        return redirect(reverse("contact:index") + "#contact-form")

    def form_invalid(self, form):
        messages.error(self.request, "Please fix the highlighted fields and try again.")
        return super().form_invalid(form)

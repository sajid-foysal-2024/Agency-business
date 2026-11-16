from unittest import mock
from urllib.parse import unquote

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from home.models import SiteSetting
from service.models import Service

from .models import ContactInquiry

OFFICE = ("House-698/15, 40 Feet Road, Block-A, Shopnodhara Housing, Bosila, "
          "Mohammadpur, Mohammadpur 1207, Bangladesh.")

VALID = {
    "full_name": "Rahim Uddin",
    "email": "Rahim@Example.com",
    "phone": "+880 1712-345678",
    "subject": "New website",
    "message": "I need a business website for my shop.",
    "website": "",
}


class ContactPageTests(TestCase):
    url = reverse("contact:index")

    def test_url_and_page(self):
        self.assertEqual(self.url, "/contact/")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for text in ["Contact Us", "Let's Talk About Your Next Project",
                     "Have an idea or a project in mind?", "Send Message", "csrfmiddlewaretoken"]:
            self.assertContains(response, text)

    def test_office_address_and_map(self):
        response = self.client.get(self.url)
        self.assertContains(response, "OS Agency Office")
        self.assertContains(response, OFFICE)
        embed = response.context["map"]["embed"]
        self.assertTrue(embed.startswith("https://www.google.com/maps?q="))
        self.assertEqual(unquote(embed.split("q=")[1].split("&")[0]), OFFICE)
        self.assertIn("output=embed", embed)
        self.assertIn("maps/dir/?api=1&destination=", response.context["map"]["directions"])
        self.assertNotIn("New York", response.content.decode())

    def test_missing_contact_details_are_hidden_not_invented(self):
        site = SiteSetting.load()
        site.phone = site.email = site.whatsapp_number = ""
        site.save()
        response = self.client.get(self.url)
        self.assertNotContains(response, "tel:")
        self.assertNotContains(response, "mailto:")
        self.assertNotContains(response, "Chat With Us")

    def test_configured_contact_details_show(self):
        site = SiteSetting.load()
        site.phone, site.email, site.whatsapp_number = "+8801700000000", "hello@osagency.com", "+8801700000000"
        site.github_url = "https://github.com/osagency"
        site.save()
        response = self.client.get(self.url)
        self.assertContains(response, "tel:+8801700000000")
        self.assertContains(response, "mailto:hello@osagency.com")
        self.assertContains(response, "Chat With Us")
        self.assertContains(response, "https://wa.me/8801700000000?text=")
        self.assertContains(response, "https://github.com/osagency")

    def test_navbar_contact_link(self):
        response = self.client.get(reverse("home:index"))
        self.assertContains(response, 'href="/contact/" class="nav-item nav-link"')

    def test_service_preselected_from_query(self):
        web = Service.objects.create(title="Web Development", description="x")
        response = self.client.get(self.url, {"service": web.slug})
        self.assertEqual(response.context["form"].initial["service"], web)


class ContactSubmitTests(TestCase):
    url = reverse("contact:index")

    def test_valid_submission_saves_and_redirects(self):
        web = Service.objects.create(title="Web Development", description="x")
        response = self.client.post(self.url, {**VALID, "service": web.pk})
        self.assertRedirects(response, self.url + "#contact-form", fetch_redirect_response=False)
        inquiry = ContactInquiry.objects.get()
        self.assertEqual(inquiry.email, "rahim@example.com")
        self.assertEqual(inquiry.service, web)
        self.assertEqual(inquiry.status, ContactInquiry.STATUS_PENDING)

        page = self.client.get(self.url)
        self.assertContains(page, "Thank you! Your message has been received.")
        # Success notice is shown once only
        self.assertNotContains(self.client.get(self.url), "Thank you! Your message has been received.")

    def test_required_fields_and_data_kept_on_error(self):
        response = self.client.post(self.url, {**VALID, "email": "not-an-email", "subject": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactInquiry.objects.count(), 0)
        form = response.context["form"]
        self.assertIn("email", form.errors)
        self.assertIn("subject", form.errors)
        self.assertContains(response, 'value="Rahim Uddin"')           # data preserved
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, "Please fix the highlighted fields")

    def test_bad_phone_and_short_message(self):
        response = self.client.post(self.url, {**VALID, "phone": "call me", "message": "hi"})
        self.assertIn("phone", response.context["form"].errors)
        self.assertIn("message", response.context["form"].errors)

    def test_phone_is_optional(self):
        self.client.post(self.url, {**VALID, "phone": ""})
        self.assertEqual(ContactInquiry.objects.count(), 1)

    def test_duplicate_submission_is_saved_once(self):
        self.client.post(self.url, VALID)
        self.client.post(self.url, VALID)
        self.assertEqual(ContactInquiry.objects.count(), 1)

    def test_honeypot_blocks_bots(self):
        self.client.post(self.url, {**VALID, "website": "http://spam.example"})
        self.assertEqual(ContactInquiry.objects.count(), 0)

    def test_csrf_required(self):
        from django.test import Client
        response = Client(enforce_csrf_checks=True).post(self.url, VALID)
        self.assertEqual(response.status_code, 403)


class NotificationTests(TestCase):
    url = reverse("contact:index")

    def test_email_sent_when_agency_email_configured(self):
        site = SiteSetting.load()
        site.notification_email = "hello@osagency.com"
        site.save()
        self.client.post(self.url, VALID)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["hello@osagency.com"])
        self.assertIn("New website", mail.outbox[0].subject)
        self.assertIn("rahim@example.com", mail.outbox[0].body)
        self.assertTrue(ContactInquiry.objects.get().notification_sent)

    def test_no_email_without_agency_email(self):
        self.client.post(self.url, VALID)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(ContactInquiry.objects.get().notification_sent)

    def test_failed_email_still_saves_and_is_not_marked_sent(self):
        site = SiteSetting.load()
        site.notification_email = "hello@osagency.com"
        site.save()
        with mock.patch("contact.services.send_mail", side_effect=OSError("SMTP down")):
            response = self.client.post(self.url, VALID)
        self.assertEqual(response.status_code, 302)
        inquiry = ContactInquiry.objects.get()
        self.assertFalse(inquiry.notification_sent)
        page = self.client.get(self.url).content.decode()
        self.assertNotIn("email was sent", page.lower())


class ContactAdminTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser("admin", "a@b.com", "pass12345")
        self.client.force_login(user)
        self.inquiry = ContactInquiry.objects.create(full_name="Karim", email="k@example.com",
                                                     subject="App", message="Need an app please")

    def test_admin_list_search_filter_and_detail(self):
        base = reverse("admin:contact_contactinquiry_changelist")
        self.assertContains(self.client.get(base), "Karim")
        self.assertContains(self.client.get(base, {"q": "Karim"}), "Karim")
        self.assertEqual(self.client.get(base, {"status__exact": "pending"}).status_code, 200)
        change = reverse("admin:contact_contactinquiry_change", args=[self.inquiry.pk])
        self.assertContains(self.client.get(change), "Need an app please")

    def test_mark_contacted_action(self):
        self.client.post(reverse("admin:contact_contactinquiry_changelist"),
                         {"action": "mark_contacted", "_selected_action": [self.inquiry.pk]})
        self.inquiry.refresh_from_db()
        self.assertEqual(self.inquiry.status, ContactInquiry.STATUS_CONTACTED)


class NotificationEmailPrivacyTests(TestCase):
    def test_notification_email_is_used_but_never_shown(self):
        site = SiteSetting.load()
        site.notification_email = "private-inbox@example.com"
        site.email = ""
        site.save()
        self.client.post(reverse("contact:index"), VALID)
        self.assertEqual(mail.outbox[0].to, ["private-inbox@example.com"])
        for url in [reverse("contact:index"), reverse("home:index")]:
            self.assertNotContains(self.client.get(url), "private-inbox@example.com")

    def test_falls_back_to_public_email(self):
        site = SiteSetting.load()
        site.email = "public@example.com"
        site.save()
        self.client.post(reverse("contact:index"), VALID)
        self.assertEqual(mail.outbox[0].to, ["public@example.com"])

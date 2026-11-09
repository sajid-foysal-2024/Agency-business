from django.test import TestCase
from django.urls import reverse

from .models import HomePage, Service, SiteSetting, Subscriber, TeamMember


class HomePageTests(TestCase):
    def test_home_renders_with_empty_database(self):
        response = self.client.get(reverse("home:index"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/index.html")
        # Fallback hero uses the brand name when there are no slides
        self.assertContains(response, SiteSetting.load().brand_name)

    def test_site_settings_change_shows_on_page(self):
        site = SiteSetting.load()
        site.brand_name = "My Brand"
        site.facebook_url = "https://facebook.com/mybrand"
        site.save()
        response = self.client.get(reverse("home:index"))
        self.assertContains(response, "My Brand")
        self.assertContains(response, "https://facebook.com/mybrand")

    def test_hidden_items_are_not_shown(self):
        Service.objects.create(title="Visible Service", description="x")
        Service.objects.create(title="Hidden Service", description="x", is_active=False)
        response = self.client.get(reverse("home:index"))
        self.assertContains(response, "Visible Service")
        self.assertNotContains(response, "Hidden Service")

    def test_section_titles_come_from_admin(self):
        page = HomePage.load()
        page.services_title = "What We Do Best"
        page.save()
        Service.objects.create(title="Web", description="x")
        response = self.client.get(reverse("home:index"))
        self.assertContains(response, "What We Do Best")

    def test_team_member_shows_role(self):
        TeamMember.objects.create(name="Sajid", role="Developer", photo="team/a.jpg")
        response = self.client.get(reverse("home:index"))
        self.assertContains(response, "Developer")

    def test_singleton_always_uses_one_row(self):
        SiteSetting(brand_name="A").save()
        SiteSetting(brand_name="B").save()
        self.assertEqual(SiteSetting.objects.count(), 1)
        self.assertEqual(SiteSetting.load().brand_name, "B")


class SubscribeTests(TestCase):
    url = reverse("home:subscribe")

    def test_subscribe_saves_lowercase_email(self):
        response = self.client.post(self.url, {"email": " Test@Example.com "})
        self.assertRedirects(response, reverse("home:index") + "#newsletter", fetch_redirect_response=False)
        self.assertTrue(Subscriber.objects.filter(email="test@example.com").exists())

    def test_duplicate_subscribe_does_not_create_second_row(self):
        self.client.post(self.url, {"email": "a@b.com"})
        self.client.post(self.url, {"email": "a@b.com"})
        self.assertEqual(Subscriber.objects.count(), 1)

    def test_invalid_email_is_rejected(self):
        self.client.post(self.url, {"email": "not-an-email"})
        self.assertEqual(Subscriber.objects.count(), 0)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

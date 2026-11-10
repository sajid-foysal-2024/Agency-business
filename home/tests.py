from django.test import TestCase
from django.urls import reverse

from developers.models import Developer

from .models import HomePage, Service, SiteSetting, Subscriber


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

    def test_team_section_shows_home_page_developers(self):
        dev = Developer.objects.create(name="Sajid Foysal", designation="Web Developer")
        Developer.objects.create(name="Hidden Dev", show_on_home=False)
        response = self.client.get(reverse("home:index"))
        self.assertContains(response, "Web Developer")
        self.assertContains(response, dev.get_absolute_url())
        self.assertNotContains(response, "Hidden Dev")

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


class ProfessionalSectionsTests(TestCase):
    """Stats, features, works, process, clients, CTA and footer."""

    def test_starter_sections_render(self):
        # Starter features + process steps come from migration 0006
        response = self.client.get(reverse("home:index"))
        self.assertContains(response, "What Makes Us Different")
        self.assertContains(response, "Skilled Team")
        self.assertContains(response, "How We Work")
        self.assertContains(response, "Launch &amp; Support")
        self.assertContains(response, 'id="cta"')

    def test_auto_stats_use_real_numbers_and_hide_zero(self):
        from developers.models import Developer
        Developer.objects.create(name="One")
        Developer.objects.create(name="Two")
        response = self.client.get(reverse("home:index"))
        labels = {s.label: s.number for s in response.context["stats"]}
        self.assertEqual(labels.get("Expert Developers"), 2)
        self.assertNotIn("Projects Completed", labels)  # 0 projects -> hidden
        self.assertNotIn("Years Experience", labels)    # no founded year yet

    def test_years_stat_uses_founded_year(self):
        from django.utils import timezone
        site = SiteSetting.load()
        site.founded_year = timezone.now().year - 5
        site.save()
        response = self.client.get(reverse("home:index"))
        labels = {s.label: s.number for s in response.context["stats"]}
        self.assertEqual(labels["Years Experience"], 5)

    def test_featured_projects_section(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from developers.models import Developer, Project
        import tempfile
        with self.settings(MEDIA_ROOT=tempfile.mkdtemp()):
            dev = Developer.objects.create(name="Sajid")
            gif = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04"
                   b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
            Project.objects.create(developer=dev, title="Shop Website",
                                   image=SimpleUploadedFile("a.gif", gif, "image/gif"))
            Project.objects.create(developer=dev, title="Not Featured", is_featured=False,
                                   image=SimpleUploadedFile("b.gif", gif, "image/gif"))
            response = self.client.get(reverse("home:index"))
        self.assertContains(response, "Shop Website")
        self.assertNotContains(response, "Not Featured")

    def test_footer_lists_services_and_contact(self):
        Service.objects.create(title="Video Editing", description="x")
        site = SiteSetting.load()
        site.email = "hello@agency.com"
        site.save()
        response = self.client.get(reverse("home:index"))
        self.assertContains(response, "Quick Links")
        self.assertContains(response, "Video Editing")
        self.assertContains(response, "mailto:hello@agency.com")

    def test_cta_and_header_button_can_be_hidden(self):
        page = HomePage.load()
        page.show_cta = False
        page.save()
        site = SiteSetting.load()
        site.header_button_text = ""
        site.save()
        response = self.client.get(reverse("home:index"))
        self.assertNotContains(response, 'id="cta"')
        self.assertNotContains(response, "header-btn")

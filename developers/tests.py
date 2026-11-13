import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ClientReview, Developer, DeveloperService, Project, Skill

# 1x1 transparent GIF, so tests do not depend on real image files
TINY_GIF = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04"
            b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")


def image(name="test.gif"):
    return SimpleUploadedFile(name, TINY_GIF, content_type="image/gif")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DeveloperModelTests(TestCase):
    def test_slug_is_created_and_unique(self):
        a = Developer.objects.create(name="Sajid Foysal")
        b = Developer.objects.create(name="Sajid Foysal")
        self.assertEqual(a.slug, "sajid-foysal")
        self.assertEqual(b.slug, "sajid-foysal-2")

    def test_non_latin_name_gets_fallback_slug(self):
        dev = Developer.objects.create(name="সাজিদ")
        self.assertEqual(dev.slug, "developer")

    def test_project_slug_unique_per_developer_only(self):
        a = Developer.objects.create(name="A")
        b = Developer.objects.create(name="B")
        p1 = Project.objects.create(developer=a, title="Shop App", image=image())
        p2 = Project.objects.create(developer=a, title="Shop App", image=image())
        p3 = Project.objects.create(developer=b, title="Shop App", image=image())
        self.assertEqual([p1.slug, p2.slug, p3.slug], ["shop-app", "shop-app-2", "shop-app"])

    def test_helpers(self):
        dev = Developer(name="Sajid Foysal", bio="One.\n\nTwo.", github_url="https://github.com/x")
        self.assertEqual(dev.first_name, "Sajid")
        self.assertEqual(dev.initials, "SF")
        self.assertEqual(dev.bio_paragraphs, ["One.", "Two."])
        self.assertEqual(dev.social_links[0]["name"], "GitHub")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DeveloperPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dev = Developer.objects.create(
            name="Sajid Foysal", designation="Full Stack Developer",
            headline="I build clean websites.", bio="Para one.\n\nPara two.",
            email="sajid@example.com", linkedin_url="https://linkedin.com/in/x",
        )
        Skill.objects.create(developer=cls.dev, name="Django", percentage=90)
        DeveloperService.objects.create(developer=cls.dev, title="Web Development")
        ClientReview.objects.create(developer=cls.dev, client_name="Kalvin", message="Great work!")
        ClientReview.objects.create(developer=cls.dev, client_name="Hidden Client", message="x", is_active=False)
        cls.projects = [
            Project.objects.create(developer=cls.dev, title=f"Project {i}", category="Web" if i % 2 else "App",
                                   image=image(), order=i)
            for i in range(1, 7)
        ]
        Project.objects.create(developer=cls.dev, title="Secret Project", image=image(), is_active=False)
        cls.hidden_dev = Developer.objects.create(name="Former Employee", is_active=False)

    def test_list_shows_only_active_developers(self):
        response = self.client.get(reverse("developers:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sajid Foysal")
        self.assertContains(response, "Full Stack Developer")
        self.assertNotContains(response, "Former Employee")

    def test_team_page_heading_and_learn_more_link(self):
        response = self.client.get(reverse("developers:list"))
        self.assertContains(response, "Meet the Whole Team")
        self.assertContains(response, "The creative minds and talented developers")
        self.assertContains(response, "Learn More")
        self.assertContains(response, f'href="{self.dev.get_absolute_url()}"')

    def test_team_profiles_alternate_left_and_right(self):
        Developer.objects.create(name="Second Dev")
        Developer.objects.create(name="Third Dev")
        html = self.client.get(reverse("developers:list")).content.decode()
        profiles = html.split('<article class="team-profile')[1:]
        self.assertEqual(len(profiles), 3)
        right = [p.startswith(" row g-5 align-items-center team-profile-right") for p in profiles]
        self.assertEqual(right, [True, False, True])  # 1st right, 2nd left, 3rd right

    def test_team_summary_falls_back_to_headline(self):
        self.assertEqual(self.dev.team_summary, "I build clean websites.")
        self.dev.short_description = "Builds Django backends."
        self.assertEqual(self.dev.team_summary, "Builds Django backends.")

    def test_portfolio_page_shows_all_sections(self):
        response = self.client.get(self.dev.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        for text in ["Hi there, I am Sajid", "I build clean websites.", "Para two.", "Django",
                     "Web Development", "Great work!", "mailto:sajid@example.com", "LinkedIn"]:
            self.assertContains(response, text)
        self.assertNotContains(response, "Hidden Client")
        self.assertNotContains(response, "Secret Project")

    def test_portfolio_shows_four_works_and_more_button(self):
        response = self.client.get(self.dev.get_absolute_url())
        self.assertEqual(len(response.context["works"]), 4)
        self.assertTrue(response.context["has_more_works"])
        self.assertContains(response, reverse("developers:works", args=[self.dev.slug]))

    def test_inactive_developer_returns_404(self):
        response = self.client.get(self.hidden_dev.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_works_page_and_category_filter(self):
        url = reverse("developers:works", args=[self.dev.slug])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["projects"]), 6)

        response = self.client.get(url, {"category": "app"})
        self.assertEqual(len(response.context["projects"]), 3)
        self.assertEqual(response.context["categories"], ["App", "Web"])

    def test_project_detail_with_neighbours(self):
        project = self.projects[1]
        response = self.client.get(project.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, project.title)
        self.assertIsNotNone(response.context["previous_project"])
        self.assertIsNotNone(response.context["next_project"])

    def test_inactive_project_returns_404(self):
        secret = Project.objects.get(title="Secret Project")
        self.assertEqual(self.client.get(secret.get_absolute_url()).status_code, 404)

    def test_empty_developer_portfolio_still_renders(self):
        empty = Developer.objects.create(name="New Joiner")
        response = self.client.get(empty.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hi there, I am New")


class AdminPageTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_superuser("admin", "a@b.com", "pass12345")
        self.client.force_login(user)
        self.dev = Developer.objects.create(name="Admin Test Dev")

    def test_admin_pages_open(self):
        urls = [
            reverse("admin:developers_developer_changelist"),
            reverse("admin:developers_developer_add"),
            reverse("admin:developers_developer_change", args=[self.dev.pk]),
            reverse("admin:developers_project_changelist"),
            reverse("admin:developers_project_add"),
            reverse("admin:home_homepage_changelist"),
            reverse("admin:home_sitesetting_changelist"),
        ]
        for url in urls:
            response = self.client.get(url, follow=True)
            self.assertEqual(response.status_code, 200, url)

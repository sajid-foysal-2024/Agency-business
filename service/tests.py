from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from home.models import SiteSetting

from .admin import PackageAdminForm
from .models import FAQ, Package, PackageFeature, Service, ServiceCategory, ServiceOffering, format_price
from .whatsapp import clean_number, package_message, whatsapp_url


def wa_text(url):
    """The decoded message inside a wa.me link."""
    return parse_qs(urlparse(url).query)["text"][0]


class PriceFormatTests(TestCase):
    def test_format(self):
        self.assertEqual(format_price(Decimal("15000"), "bdt"), "৳ 15,000")
        self.assertEqual(format_price(Decimal("149.99"), "usd"), "$ 149.99")
        self.assertEqual(format_price(Decimal("150.00"), "usd"), "$ 150")
        self.assertEqual(format_price(None, "usd"), "")


class ServiceModelTests(TestCase):
    def test_slug_from_title(self):
        self.assertEqual(Service.objects.create(title="Web Development", description="x").slug, "web-development")
        self.assertEqual(Service.objects.create(title="Web Development", description="x").slug, "web-development-2")

    def test_package_validation(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            Package(package_type=Package.SINGLE, name="No service").clean()
        service = Service.objects.create(title="Web", description="x")
        with self.assertRaises(ValidationError):
            Package(package_type=Package.COMBO, name="Combo", service=service).clean()

    def test_combo_needs_two_services_in_admin(self):
        web = Service.objects.create(title="Web", description="x")
        form = PackageAdminForm(data={"package_type": "combo", "name": "Combo", "included_services": [web.pk],
                                      "order": 0, "is_active": True, "button_text": "Order Now"})
        self.assertFalse(form.is_valid())
        self.assertIn("included_services", form.errors)


class WhatsAppTests(TestCase):
    def setUp(self):
        self.web = Service.objects.create(title="Web Development", description="x")
        self.package = Package.objects.create(service=self.web, name="Business Website",
                                              price_bdt=Decimal("25000"), price_usd=None)

    def test_number_is_cleaned(self):
        self.assertEqual(clean_number("+880 1712-345678"), "8801712345678")
        self.assertEqual(whatsapp_url("", "hi"), "")

    def test_message_matches_spec(self):
        text = package_message("OS Agency", self.package, "bdt")
        self.assertEqual(text, "Hello OS Agency!\nI am interested in your Web Development service.\n"
                               "Package: Business Website.\nCurrency: BDT.\nPrice: ৳ 25,000.\n"
                               "I would like to discuss this package.")

    def test_missing_price_is_never_invented(self):
        text = package_message("OS Agency", self.package, "usd")
        self.assertIn("Currency: USD.", text)
        self.assertIn("Price: Please share the price.", text)

    def test_url_is_encoded(self):
        url = whatsapp_url("+8801712345678", "Hello & welcome\nPrice: ৳ 1")
        self.assertTrue(url.startswith("https://wa.me/8801712345678?text="))
        self.assertNotIn(" ", url)
        self.assertEqual(wa_text(url), "Hello & welcome\nPrice: ৳ 1")


class ServicePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        site = SiteSetting.load()
        site.whatsapp_number = "+8801700000000"
        site.save()
        cls.category = ServiceCategory.objects.create(name="Development")
        cls.web = Service.objects.create(title="Web Development", description="We build websites.",
                                         category=cls.category, overview="Para one.\n\nPara two.")
        cls.app = Service.objects.create(title="App Development", description="We build apps.")
        cls.hidden = Service.objects.create(title="Old Service", description="x", is_active=False)
        ServiceOffering.objects.create(service=cls.web, title="Landing Pages")

        cls.basic = Package.objects.create(service=cls.web, name="Basic", price_bdt=Decimal("15000"),
                                           price_usd=Decimal("150"), order=1)
        PackageFeature.objects.create(package=cls.basic, text="5 pages")
        PackageFeature.objects.create(package=cls.basic, text="E-commerce", is_included=False)
        cls.business = Package.objects.create(service=cls.web, name="Business Website", is_popular=True,
                                              price_bdt=Decimal("30000"), order=2)
        Package.objects.create(service=cls.web, name="Hidden Plan", is_active=False, price_bdt=1)

        cls.combo = Package.objects.create(package_type=Package.COMBO, name="Startup Combo",
                                           price_bdt=Decimal("50000"), price_usd=Decimal("500"),
                                           discount_text="Save 10%", is_featured=True)
        cls.combo.included_services.set([cls.web, cls.app])

        FAQ.objects.create(service=cls.web, question="How long does a website take?", answer="It depends.")
        FAQ.objects.create(question="Do you offer support?", answer="Yes.")
        FAQ.objects.create(service=cls.app, question="App only question?", answer="x")

    def test_service_urls_use_slugs(self):
        self.assertEqual(self.web.get_absolute_url(), "/services/web-development/")
        self.assertEqual(reverse("services:list"), "/services/")

    def test_detail_page_sections(self):
        response = self.client.get(self.web.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        for text in ["We build websites.", "Para two.", "Landing Pages", "Choose Your Package",
                     "Basic", "Business Website", "Popular", "Startup Combo", "Save 10%",
                     "How long does a website take?", "Do you offer support?", "Chat on WhatsApp",
                     "৳ 15,000", "$ 150", "5 pages", "(not included)"]:
            self.assertContains(response, text)
        self.assertNotContains(response, "Hidden Plan")
        self.assertNotContains(response, "App only question?")

    def test_missing_usd_shows_price_on_request(self):
        response = self.client.get(self.web.get_absolute_url())
        business = next(p for p in response.context["single_packages"] if p.name == "Business Website")
        self.assertIn("Price: Please share the price.", wa_text(business.wa_usd))
        self.assertContains(response, "Price on request")

    def test_package_whatsapp_links_per_currency(self):
        response = self.client.get(self.web.get_absolute_url())
        basic = next(p for p in response.context["single_packages"] if p.name == "Basic")
        self.assertIn("Currency: BDT.\nPrice: ৳ 15,000.", wa_text(basic.wa_bdt))
        self.assertIn("Currency: USD.\nPrice: $ 150.", wa_text(basic.wa_usd))
        self.assertContains(response, 'data-href-usd="https://wa.me/8801700000000?text=')

    def test_combo_shows_on_every_included_service(self):
        response = self.client.get(self.app.get_absolute_url())
        self.assertContains(response, "Startup Combo")
        combo = response.context["combo_packages"][0]
        self.assertIn("Startup Combo combo package (Web Development, App Development)", wa_text(combo.wa_bdt))

    def test_inactive_service_404(self):
        self.assertEqual(self.client.get(self.hidden.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get("/services/does-not-exist/").status_code, 404)

    def test_list_page(self):
        response = self.client.get(reverse("services:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Development")      # category heading
        self.assertContains(response, "App Development")  # uncategorised service
        self.assertNotContains(response, "Old Service")
        self.assertContains(response, "Featured Packages")
        self.assertContains(response, "Starting from")
        self.assertContains(response, 'data-set-currency="usd"')
        web = next(s for g in response.context["categories"] for s in g["services"] if s.pk == self.web.pk)
        self.assertEqual(web.from_price_bdt, Decimal("15000"))

    def test_no_whatsapp_number_falls_back_to_contact(self):
        site = SiteSetting.load()
        site.whatsapp_number = ""
        site.save()
        response = self.client.get(self.web.get_absolute_url())
        self.assertNotContains(response, "wa.me")
        self.assertContains(response, "Contact Us")

    def test_page_without_packages_still_renders(self):
        response = self.client.get(self.app.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        empty = Service.objects.create(title="Video Editing", description="x")
        response = self.client.get(empty.get_absolute_url())
        self.assertContains(response, "coming soon")
        self.assertNotContains(response, 'data-set-currency')


class NavigationTests(TestCase):
    def test_home_services_link_to_detail_pages(self):
        web = Service.objects.create(title="Web Development", description="x")
        response = self.client.get(reverse("home:index"))
        self.assertContains(response, f'href="{web.get_absolute_url()}"')

    def test_navbar_and_footer_links(self):
        response = self.client.get(reverse("home:index"))
        self.assertContains(response, 'href="/services/"')
        self.assertContains(response, 'href="/#testimonial"')  # Shop keeps its old target
        self.assertNotContains(response, 'href="#testimonial"')
        self.assertNotContains(response, "service_url")


class AdminTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser("admin", "a@b.com", "pass12345")
        self.client.force_login(user)
        self.service = Service.objects.create(title="Web", description="x")
        self.package = Package.objects.create(service=self.service, name="Basic")

    def test_admin_pages_open(self):
        for name, args in [("service_servicecategory_changelist", []), ("service_servicecategory_add", []),
                           ("service_service_changelist", []), ("service_service_add", []),
                           ("service_service_change", [self.service.pk]),
                           ("service_package_changelist", []), ("service_package_add", []),
                           ("service_package_change", [self.package.pk]),
                           ("service_faq_changelist", []), ("home_sitesetting_changelist", [])]:
            response = self.client.get(reverse(f"admin:{name}", args=args), follow=True)
            self.assertEqual(response.status_code, 200, name)


class DemoPackagesCommandTests(TestCase):
    def setUp(self):
        self.web = Service.objects.create(title="Web Development", description="x", overview="My own overview")
        self.app = Service.objects.create(title="App Development", description="x")
        self.video = Service.objects.create(title="Video Editing", description="x")
        self.mine = Package.objects.create(service=self.web, name="My Real Package", price_usd=Decimal("999"))

    def run_command(self, *args):
        from io import StringIO
        from django.core.management import call_command
        call_command("demo_packages", *args, stdout=StringIO())

    def test_create_is_repeatable_and_marked(self):
        self.run_command()
        self.run_command()
        demo = Package.objects.filter(is_demo=True)
        self.assertEqual(demo.count(), 12)
        self.assertEqual(demo.filter(package_type=Package.COMBO).count(), 2)
        self.assertTrue(demo.filter(billing_type=Package.MONTHLY).exists())
        self.assertTrue(demo.filter(price_bdt__isnull=True, price_usd__isnull=True).exists())  # quote-only
        response = self.client.get(self.web.get_absolute_url())
        self.assertContains(response, "Sample")
        self.assertContains(response, "Business Website")

    def test_own_texts_are_not_overwritten(self):
        self.run_command()
        self.web.refresh_from_db()
        self.app.refresh_from_db()
        self.assertEqual(self.web.overview, "My own overview")
        self.assertTrue(self.app.overview)          # was empty, so filled for the preview

    def test_remove_keeps_real_data(self):
        self.run_command()
        self.run_command("--remove")
        self.assertFalse(Package.objects.filter(is_demo=True).exists())
        self.assertFalse(FAQ.objects.filter(is_demo=True).exists())
        self.assertTrue(Package.objects.filter(pk=self.mine.pk).exists())
        self.app.refresh_from_db()
        self.web.refresh_from_db()
        self.assertEqual(self.app.overview, "")          # demo text cleared
        self.assertEqual(self.web.overview, "My own overview")

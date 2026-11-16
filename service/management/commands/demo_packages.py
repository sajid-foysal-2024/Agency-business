"""Sample packages, add-ons, offerings and FAQs so the service pages can be previewed.

    python manage.py demo_packages           # create (or refresh) the demo data
    python manage.py demo_packages --remove  # delete all demo data again

Everything created here is flagged is_demo=True and shows a small "Sample" tag on
the website. USD prices sit inside the ranges proposed in the research report;
BDT prices are placeholders for preview only. Replace them with your real prices.
Your own (non-demo) data is never changed, and empty service texts are only
filled in if they are still empty.
"""
from decimal import Decimal as D

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from service.models import FAQ, AddOn, Package, PackageFeature, Service, ServiceOffering

# key -> words used to find the existing service by its title
SERVICE_KEYS = {"web": "web", "app": "app", "video": "video"}

SERVICE_TEXTS = {
    "web": {
        "delivery_time": "1-7 weeks",
        "deliverables": "Responsive website (mobile, tablet, desktop)\nContent management system\n"
                        "Basic SEO setup\nContact and lead forms\nHosting and launch support\nSource code handover",
        "overview": "We design and build fast, modern websites that work on every screen.\n\n"
                    "From a simple landing page to a full online store, every project includes clean code, "
                    "basic SEO and help with going live.",
    },
    "app": {
        "delivery_time": "8-16 weeks",
        "deliverables": "Android and iOS app from one codebase (Flutter)\nUI design for every screen\n"
                        "API and backend integration\nTesting on real devices\nApp Store and Play Store publishing",
        "overview": "We build mobile apps for Android and iOS with one shared codebase, so you launch on both "
                    "stores at once.\n\nWe handle design, development, testing and publishing.",
    },
    "video": {
        "delivery_time": "2-5 days per video",
        "deliverables": "Edited video in your chosen format\nColor correction and sound clean-up\n"
                        "Captions and titles\nBackground music (licensed)\nTwo revision rounds",
        "overview": "We turn raw footage into engaging videos for YouTube, Reels, TikTok and ads.\n\n"
                    "Send us your clips and we deliver a polished, ready-to-post video.",
    },
}

OFFERINGS = {
    "web": [("Business Websites", "fa-solid fa-briefcase", "Company sites that explain what you do and bring in leads."),
            ("Online Stores", "fa-solid fa-cart-shopping", "Product catalogue, cart, checkout and order management."),
            ("Website Care", "fa-solid fa-screwdriver-wrench", "Updates, backups and small fixes every month.")],
    "app": [("Cross-platform Apps", "fa-solid fa-mobile-screen", "One Flutter codebase for Android and iOS."),
            ("App UI Design", "fa-solid fa-pen-ruler", "Clean, easy screens designed before we code."),
            ("Store Publishing", "fa-solid fa-rocket", "We prepare and publish your app on both stores.")],
    "video": [("Short-form Videos", "fa-solid fa-bolt", "Reels, TikTok and Shorts with captions."),
              ("YouTube Editing", "fa-brands fa-youtube", "Long videos with color, sound and thumbnails."),
              ("Ad Creatives", "fa-solid fa-bullhorn", "Short ads made to stop the scroll.")],
}

# (service key, name, tagline, bdt, usd, regular_bdt, regular_usd, billing, popular, featured,
#  delivery, discount_text, [features], [not included])
PACKAGES = [
    ("web", "Starter Website", "A clean site to get you online", D("25000"), D("600"), None, None,
     "one_time", False, False, "7-10 days", "",
     ["Up to 5 pages", "Mobile responsive design", "Contact form", "Basic SEO setup", "1 revision round"],
     ["Online store"]),
    ("web", "Business Website", "For growing companies", D("65000"), D("1800"), D("75000"), D("2100"),
     "one_time", True, True, "3-4 weeks", "Save 15%",
     ["Up to 12 pages", "Content management system", "Blog section", "Speed optimization",
      "1 month free support"], []),
    ("web", "E-commerce Store", "Sell online with your own store", D("140000"), D("3500"), None, None,
     "one_time", False, False, "5-7 weeks", "",
     ["Up to 50 products", "Cart and checkout", "Payment gateway setup", "Order management",
      "1 month free support"], []),
    ("web", "Website Care Plan", "We look after your site", D("6000"), D("150"), None, None,
     "monthly", False, False, "Every month", "",
     ["Updates and backups", "Security monitoring", "Up to 5 hours of small fixes"], []),
    ("app", "App MVP", "Test your idea on real users", D("250000"), D("5000"), None, None,
     "one_time", False, False, "8-10 weeks", "",
     ["Android and iOS (Flutter)", "Up to 8 screens", "API integration", "Store publishing"],
     ["Admin dashboard"]),
    ("app", "Business App", "A complete app for your business", D("450000"), D("9000"), None, None,
     "one_time", True, True, "12-16 weeks", "",
     ["Android and iOS (Flutter)", "Up to 20 screens", "Admin dashboard", "Push notifications",
      "3 months free support"], []),
    ("app", "Enterprise App", "Large or complex projects", None, None, None, None,
     "one_time", False, False, "", "",
     ["Custom architecture", "Integrations with your systems", "Dedicated team"], []),
    ("video", "Short-form Video", "One Reel, TikTok or Short", D("2500"), D("60"), None, None,
     "one_time", False, False, "2-3 days", "",
     ["Up to 60 seconds", "Captions", "Background music", "2 revision rounds"], []),
    ("video", "YouTube Video", "Long-form editing", D("10000"), D("250"), None, None,
     "one_time", True, False, "4-5 days", "",
     ["8-15 minute edit", "Color and sound", "Custom thumbnail", "2 revision rounds"], []),
    ("video", "Monthly Content Plan", "Fresh videos every month", D("30000"), D("750"), D("36000"), D("900"),
     "monthly", False, True, "Every month", "Save 17%",
     ["12 short videos a month", "Content calendar", "Captions on every video", "Priority delivery"], []),
]

# (name, tagline, bdt, usd, regular_bdt, regular_usd, [service keys], popular, featured, discount, [features])
COMBOS = [
    ("Startup Launch Combo", "Website plus launch videos", D("80000"), D("2200"), D("90000"), D("2450"),
     ["web", "video"], True, True, "Save 10%",
     ["Business Website package", "4 short launch videos", "Social media cover designs"]),
    ("Digital Growth Combo", "Website, app and monthly videos", D("520000"), D("11500"), None, None,
     ["web", "app", "video"], False, False, "",
     ["Business Website package", "App MVP package", "First month of the Content Plan"]),
]

# (service key or None for every service, name, description, bdt, usd)
ADDONS = [
    ("web", "Rush delivery", "We start right away and deliver faster", D("6000"), D("150")),
    ("web", "Extra page", "One more page on your website", D("2000"), D("50")),
    ("app", "Extra screen", "One more app screen", D("12000"), D("300")),
    ("video", "Second-language subtitles", "Subtitles in one more language", D("800"), D("20")),
    (None, "Logo design", "A simple, modern logo", D("5000"), D("120")),
    (None, "Domain and hosting setup", "Available in Bangladesh pricing only", D("3000"), None),
]

FAQS = [
    ("web", "How long does a website take?", "Most websites take 1 to 4 weeks. Online stores take longer."),
    ("web", "Can I update the website myself?", "Yes. Business and store packages include a content management system."),
    ("app", "Do you publish the app for me?", "Yes. We publish to the Google Play Store and the Apple App Store."),
    ("video", "How do I send my footage?", "Share a Google Drive or Dropbox link after you order."),
    (None, "Can I pay in BDT or USD?", "Yes. Choose your currency at the top of the pricing section."),
]


class Command(BaseCommand):
    help = "Create (or with --remove, delete) sample packages so the service pages can be previewed."

    def add_arguments(self, parser):
        parser.add_argument("--remove", action="store_true", help="Delete all demo data.")

    def find_services(self):
        services = {}
        for key, word in SERVICE_KEYS.items():
            service = Service.objects.filter(title__icontains=word).order_by("order", "id").first()
            if service is None:
                raise CommandError(f'No service with "{word}" in its title. Add it in the admin first.')
            services[key] = service
        return services

    def remove_demo(self, services):
        counts = [model.objects.filter(is_demo=True).delete()[0]
                  for model in (Package, AddOn, ServiceOffering, FAQ)]
        # Clear the service texts only if they are still exactly the demo texts
        for key, service in services.items():
            changed = [f for f, value in SERVICE_TEXTS[key].items() if getattr(service, f) == value]
            for f in changed:
                setattr(service, f, "")
            if changed:
                service.save(update_fields=changed)
        return sum(counts)

    @transaction.atomic
    def handle(self, *args, **options):
        services = self.find_services()
        removed = self.remove_demo(services)
        if options["remove"]:
            self.stdout.write(self.style.SUCCESS(f"Removed demo data ({removed} rows)."))
            return

        for key, service in services.items():
            empty = [f for f, value in SERVICE_TEXTS[key].items() if not getattr(service, f)]
            for f in empty:
                setattr(service, f, SERVICE_TEXTS[key][f])
            if empty:
                service.save(update_fields=empty)
            for i, (title, icon, text) in enumerate(OFFERINGS[key], start=1):
                ServiceOffering.objects.create(service=service, title=title, icon=icon, description=text,
                                               order=i, is_demo=True)

        for i, (key, name, tagline, bdt, usd, rbdt, rusd, billing, popular, featured, delivery, discount,
                features, missing) in enumerate(PACKAGES, start=1):
            package = Package.objects.create(
                service=services[key], name=name, tagline=tagline, price_bdt=bdt, price_usd=usd,
                regular_price_bdt=rbdt, regular_price_usd=rusd, billing_type=billing, is_popular=popular,
                is_featured=featured, delivery_time=delivery, discount_text=discount, order=i, is_demo=True,
                price_note="per month" if billing == "monthly" else "",
            )
            self.add_features(package, features, missing)

        for i, (name, tagline, bdt, usd, rbdt, rusd, keys, popular, featured, discount, features) in enumerate(
                COMBOS, start=1):
            combo = Package.objects.create(
                package_type=Package.COMBO, name=name, tagline=tagline, price_bdt=bdt, price_usd=usd,
                regular_price_bdt=rbdt, regular_price_usd=rusd, is_popular=popular, is_featured=featured,
                discount_text=discount, order=i, is_demo=True,
            )
            combo.included_services.set([services[k] for k in keys])
            self.add_features(combo, features, [])

        for i, (key, name, description, bdt, usd) in enumerate(ADDONS, start=1):
            AddOn.objects.create(service=services[key] if key else None, name=name, description=description,
                                 price_bdt=bdt, price_usd=usd, order=i, is_demo=True)

        for i, (key, question, answer) in enumerate(FAQS, start=1):
            FAQ.objects.create(service=services[key] if key else None, question=question, answer=answer,
                               order=i, is_demo=True)

        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready: {len(PACKAGES)} packages, {len(COMBOS)} combos, {len(ADDONS)} add-ons, "
            f"{len(FAQS)} FAQs. Remove it any time with: python manage.py demo_packages --remove"))

    @staticmethod
    def add_features(package, included, missing):
        for i, text in enumerate(included, start=1):
            PackageFeature.objects.create(package=package, text=text, order=i)
        for i, text in enumerate(missing, start=len(included) + 1):
            PackageFeature.objects.create(package=package, text=text, is_included=False, order=i)

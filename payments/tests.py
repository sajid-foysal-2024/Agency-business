"""End-to-end tests for checkout, sandbox payments, webhooks, SSLCOMMERZ (mocked), refunds and invoices."""
import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from orders.models import Invoice, Order
from orders.services import create_order, create_order_from_quote
from service.models import AddOn, Package, QuoteRequest, Service

from .apps import check_payment_settings
from .models import Payment, PaymentEvent, PaymentMethodConfig
from .providers import available_methods
from .providers.demo import build_event, sign
from .services import PaymentError, refund_payment, start_payment

CONTACT = {"full_name": "Jane Client", "email": "jane@example.com", "phone": "+1 555 123 4567",
           "company": "Acme", "country": "United States", "notes": "Please start soon"}


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("jane@example.com", "jane@example.com", "pass12345!",
                                            first_name="Jane")
        cls.other = User.objects.create_user("bob@example.com", "bob@example.com", "pass12345!")
        cls.service = Service.objects.create(title="Web Development", description="We build websites.")
        cls.package = Package.objects.create(service=cls.service, name="Business Website",
                                             price_bdt=Decimal("15000"), price_usd=Decimal("150"))
        cls.bdt_only = Package.objects.create(service=cls.service, name="Local Plan", price_bdt=Decimal("5000"))
        cls.addon = AddOn.objects.create(service=cls.service, name="Rush delivery",
                                         price_bdt=Decimal("2000"), price_usd=Decimal("20"))
        cls.usd_only_addon = AddOn.objects.create(name="Extra revision", price_usd=Decimal("10"))

    def setUp(self):
        cache.clear()
        self.client.force_login(self.user)

    def make_order(self, currency="usd", addons=None, package=None):
        return create_order(self.user, package or self.package, currency, addons or [], CONTACT)

    def start_demo(self, order):
        response = self.client.post(reverse("orders:review", args=[order.number]), {"method": "demo"})
        return response, order.payments.get(status=Payment.PENDING)


class CheckoutTests(Base):
    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("orders:checkout", args=[self.package.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_checkout_page(self):
        response = self.client.get(reverse("orders:checkout", args=[self.package.pk]), {"currency": "bdt"})
        self.assertContains(response, "Business Website")
        self.assertContains(response, "DEMO PAYMENT MODE")
        self.assertContains(response, "৳ 15,000")
        self.assertEqual(response.context["currency"], "bdt")

    def test_server_side_prices_ignore_posted_prices(self):
        response = self.client.post(reverse("orders:checkout", args=[self.package.pk]), {
            **CONTACT, "currency": "usd", "addons": [self.addon.pk, self.usd_only_addon.pk],
            "price": "1", "total": "1", "unit_price": "1",   # tampering attempts
        })
        order = Order.objects.get()
        self.assertRedirects(response, reverse("orders:review", args=[order.number]))
        self.assertEqual(order.total, Decimal("180"))   # 150 + 20 + 10
        self.assertEqual(order.status, Order.DRAFT)
        self.assertEqual(order.items.count(), 3)

    def test_addon_without_price_in_currency_is_rejected(self):
        self.client.post(reverse("orders:checkout", args=[self.package.pk]),
                         {**CONTACT, "currency": "bdt", "addons": [self.usd_only_addon.pk]})
        self.assertEqual(Order.objects.count(), 0)

    def test_currency_without_price_cannot_be_used(self):
        self.client.post(reverse("orders:checkout", args=[self.bdt_only.pk]), {**CONTACT, "currency": "usd"})
        self.assertEqual(Order.objects.count(), 0)
        response = self.client.get(reverse("orders:checkout", args=[self.bdt_only.pk]), {"currency": "usd"})
        self.assertEqual(response.context["currency"], "bdt")

    def test_package_without_any_price_404(self):
        no_price = Package.objects.create(service=self.service, name="Custom")
        self.assertEqual(self.client.get(reverse("orders:checkout", args=[no_price.pk])).status_code, 404)

    def test_service_page_links_to_checkout_and_quote(self):
        response = self.client.get(self.service.get_absolute_url())
        self.assertContains(response, f'{reverse("orders:checkout", args=[self.package.pk])}?currency=usd')
        self.assertContains(response, "Request a Quote")   # Local Plan has no USD price
        self.assertContains(response, "Request a Custom Quote")
        self.assertContains(response, "Rush delivery")

    def test_rate_limit(self):
        url = reverse("orders:checkout", args=[self.package.pk])
        codes = [self.client.post(url, {"currency": "usd"}).status_code for _ in range(16)]
        self.assertEqual(codes[-1], 429)


class DemoPaymentTests(Base):
    def test_full_success_flow(self):
        order = self.make_order("usd", [self.addon])
        review = self.client.get(reverse("orders:review", args=[order.number]))
        self.assertContains(review, "Demo payment (test only)")

        response, payment = self.start_demo(order)
        self.assertRedirects(response, reverse("payments:demo", args=[payment.reference]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.PENDING_PAYMENT)
        self.assertTrue(Invoice.objects.filter(order=order, status=Invoice.UNPAID).exists())

        demo = self.client.get(reverse("payments:demo", args=[payment.reference]))
        self.assertContains(demo, "NOT A REAL PAYMENT")

        with self.captureOnCommitCallbacks(execute=True):   # emails are sent after the DB commit
            self.client.post(reverse("payments:demo", args=[payment.reference]), {"outcome": "success"})
        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(order.status, Order.PAID)
        self.assertEqual(payment.status, Payment.SUCCEEDED)
        self.assertTrue(payment.is_sandbox)
        self.assertEqual(order.invoice.status, Invoice.PAID)
        self.assertEqual(mail.outbox[0].to, ["jane@example.com"])
        self.assertIn(order.number, mail.outbox[0].subject)
        self.assertEqual(PaymentEvent.objects.filter(payment=payment).count(), 1)

    def test_failure_then_retry(self):
        order = self.make_order()
        _, payment = self.start_demo(order)
        self.client.post(reverse("payments:demo", args=[payment.reference]), {"outcome": "failure"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.FAILED)
        self.assertContains(self.client.get(order.get_absolute_url()), "Try payment again")

        _, retry = self.start_demo(order)
        self.client.post(reverse("payments:demo", args=[retry.reference]), {"outcome": "success"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.PAID)

    def test_cancel_and_pending(self):
        order = self.make_order()
        _, payment = self.start_demo(order)
        self.client.post(reverse("payments:demo", args=[payment.reference]), {"outcome": "pending"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.PAYMENT_PROCESSING)

        self.client.post(reverse("payments:demo", args=[payment.reference]), {"outcome": "cancel"})
        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.CANCELLED)
        self.assertEqual(order.status, Order.PENDING_PAYMENT)   # can still pay

    def test_return_page_alone_never_marks_paid(self):
        order = self.make_order()
        _, payment = self.start_demo(order)
        self.client.get(order.get_absolute_url())
        self.client.get(reverse("payments:sslcommerz_return", args=["success"]), {"tran_id": payment.reference})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.PENDING_PAYMENT)

    def test_customer_can_cancel_unpaid_order(self):
        order = self.make_order()
        self.client.post(reverse("orders:cancel", args=[order.number]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.CANCELLED)
        with self.assertRaises(PaymentError):
            start_payment(order, "demo", None)


class WebhookTests(Base):
    url = reverse("payments:demo_webhook")

    def post_event(self, body, signature):
        return self.client.post(self.url, body, content_type="application/json", HTTP_X_DEMO_SIGNATURE=signature)

    def test_signature_required(self):
        order = self.make_order()
        _, payment = self.start_demo(order)
        body, _ = build_event(payment, "success")
        self.assertEqual(self.post_event(body, "bad").status_code, 400)
        self.assertEqual(self.post_event(body, "").status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.PENDING_PAYMENT)

    def test_duplicate_webhook_is_processed_once(self):
        order = self.make_order()
        _, payment = self.start_demo(order)
        body, signature = build_event(payment, "success")
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.post_event(body, signature).content, b"applied success")
            self.assertEqual(self.post_event(body, signature).content, b"duplicate ignored")
        self.assertEqual(PaymentEvent.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_late_failure_after_success_is_ignored(self):
        order = self.make_order()
        _, payment = self.start_demo(order)
        self.post_event(*build_event(payment, "success"))
        self.post_event(*build_event(payment, "failure"))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.PAID)

    def test_wrong_amount_is_rejected(self):
        order = self.make_order()
        _, payment = self.start_demo(order)
        body = json.dumps({"event_id": "e1", "reference": payment.reference, "outcome": "success",
                           "amount": "1.00", "currency": "usd"}).encode()
        self.post_event(body, sign(body))
        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.FAILED)
        self.assertIn("mismatch", payment.failure_reason)
        self.assertNotEqual(order.status, Order.PAID)

    def test_no_double_successful_payment(self):
        order = self.make_order()
        _, payment = self.start_demo(order)
        self.post_event(*build_event(payment, "success"))
        with self.assertRaises(PaymentError):
            start_payment(order, "demo", None)
        with self.assertRaises(IntegrityError):
            Payment.objects.create(order=order, provider="demo", amount=order.total, currency="usd",
                                   status=Payment.SUCCEEDED)


class OwnershipTests(Base):
    def test_other_customer_cannot_see_or_pay(self):
        order = self.make_order()
        _, payment = self.start_demo(order)
        self.client.force_login(self.other)
        for url in [order.get_absolute_url(), reverse("orders:review", args=[order.number]),
                    reverse("orders:invoice", args=[order.number]),
                    reverse("payments:demo", args=[payment.reference])]:
            self.assertEqual(self.client.get(url).status_code, 404, url)
        self.assertEqual(self.client.post(reverse("payments:demo", args=[payment.reference]),
                                          {"outcome": "success"}).status_code, 404)
        order.refresh_from_db()
        self.assertNotEqual(order.status, Order.PAID)


class ModeTests(Base):
    @override_settings(PAYMENT_MODE="live", SSLCOMMERZ_STORE_ID="", SSLCOMMERZ_STORE_PASSWORD="",
                       DEBUG=False, SITE_URL="https://osagency.example")
    def test_live_mode_hides_demo_and_requires_credentials(self):
        self.assertEqual([c.code for c, _ in available_methods("usd")], [])
        order = self.make_order()
        payment = Payment.objects.create(order=order, provider="demo", amount=order.total, currency="usd")
        self.assertEqual(self.client.get(reverse("payments:demo", args=[payment.reference])).status_code, 404)
        self.assertEqual(self.client.post(reverse("payments:demo_webhook")).status_code, 404)
        self.assertIn("payments.E002", [e.id for e in check_payment_settings()])

    @override_settings(PAYMENT_MODE="maybe")
    def test_bad_mode_is_an_error(self):
        self.assertIn("payments.E001", [e.id for e in check_payment_settings()])

    def test_sandbox_has_no_errors(self):
        self.assertEqual(check_payment_settings(), [])


@override_settings(SSLCOMMERZ_STORE_ID="store_from_env", SSLCOMMERZ_STORE_PASSWORD="secret_from_env")
class SSLCommerzTests(Base):
    """SSLCOMMERZ's servers are replaced by a fake http_call; no network, no real credentials."""

    def setUp(self):
        super().setUp()
        PaymentMethodConfig.objects.filter(code="sslcommerz").update(is_enabled=True)
        self.order = self.make_order("bdt", [self.addon])   # 17,000 BDT

    def start(self):
        session = {"status": "SUCCESS", "sessionkey": "S123",
                   "GatewayPageURL": "https://sandbox.sslcommerz.com/EasyCheckOut/abc"}
        with mock.patch("payments.providers.sslcommerz.http_call", return_value=session) as call:
            response = self.client.post(reverse("orders:review", args=[self.order.number]), {"method": "sslcommerz"})
        sent = call.call_args.args[2]
        return response, Payment.objects.get(order=self.order, status=Payment.PENDING), sent

    def validation(self, payment, **overrides):
        data = {"status": "VALID", "tran_id": payment.reference, "amount": "17000.00", "currency": "BDT",
                "bank_tran_id": "BANK1", "card_no": "411111XXXXXX1111"}
        data.update(overrides)
        return data

    def test_start_redirects_to_gateway(self):
        response, payment, sent = self.start()
        self.assertEqual(response["Location"], "https://sandbox.sslcommerz.com/EasyCheckOut/abc")
        self.assertEqual(sent["total_amount"], "17000.00")
        self.assertEqual(sent["currency"], "BDT")
        self.assertEqual(sent["tran_id"], payment.reference)
        self.assertTrue(sent["ipn_url"].endswith(reverse("payments:sslcommerz_ipn")))

    def test_ipn_validated_payment_marks_paid(self):
        _, payment, _ = self.start()
        with mock.patch("payments.providers.sslcommerz.http_call", return_value=self.validation(payment)) as call:
            self.client.post(reverse("payments:sslcommerz_ipn"),
                             {"status": "VALID", "tran_id": payment.reference, "val_id": "V1"})
            # Same IPN again: no second validation call, no change
            self.client.post(reverse("payments:sslcommerz_ipn"),
                             {"status": "VALID", "tran_id": payment.reference, "val_id": "V1"})
        self.assertEqual(call.call_count, 1)
        self.assertIn("validationserverAPI", call.call_args.args[1])
        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.PAID)
        self.assertEqual(payment.provider_transaction_id, "BANK1")
        self.assertNotIn("card_no", payment.raw_response)   # card data never stored

    def test_validation_amount_mismatch_fails(self):
        _, payment, _ = self.start()
        with mock.patch("payments.providers.sslcommerz.http_call",
                        return_value=self.validation(payment, amount="10.00")):
            self.client.post(reverse("payments:sslcommerz_ipn"),
                             {"status": "VALID", "tran_id": payment.reference, "val_id": "V2"})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.FAILED)

    def test_invalid_validation_is_not_paid(self):
        _, payment, _ = self.start()
        with mock.patch("payments.providers.sslcommerz.http_call",
                        return_value={"status": "INVALID_TRANSACTION"}):
            self.client.post(reverse("payments:sslcommerz_return", args=["success"]),
                             {"status": "VALID", "tran_id": payment.reference, "val_id": "V3"})
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.status, Order.PAID)

    def test_usd_payment_checks_currency_amount(self):
        order = self.make_order("usd")
        self.order = order
        _, payment, _ = self.start()
        good = {"status": "VALID", "tran_id": payment.reference, "amount": "18000.00", "currency": "BDT",
                "currency_type": "USD", "currency_amount": "150.00", "bank_tran_id": "B2"}
        with mock.patch("payments.providers.sslcommerz.http_call", return_value=good):
            self.client.post(reverse("payments:sslcommerz_ipn"),
                             {"status": "VALID", "tran_id": payment.reference, "val_id": "V4"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.PAID)

    def test_failed_and_cancelled_ipn(self):
        _, payment, _ = self.start()
        self.client.post(reverse("payments:sslcommerz_ipn"), {"status": "CANCELLED", "tran_id": payment.reference})
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.CANCELLED)

    def test_refund_call(self):
        _, payment, _ = self.start()
        with mock.patch("payments.providers.sslcommerz.http_call", return_value=self.validation(payment)):
            self.client.post(reverse("payments:sslcommerz_ipn"),
                             {"status": "VALID", "tran_id": payment.reference, "val_id": "V5"})
        payment.refresh_from_db()
        with mock.patch("payments.providers.sslcommerz.http_call",
                        return_value={"status": "success", "refund_ref_id": "R1"}) as call:
            refund = refund_payment(payment, Decimal("17000"), "Client request")
        self.assertEqual(call.call_args.args[2]["bank_tran_id"], "BANK1")
        self.assertEqual(refund.provider_refund_id, "R1")
        self.assertEqual(refund.status, "pending")   # SSLCOMMERZ processes refunds asynchronously


class RefundTests(Base):
    def test_demo_full_refund(self):
        order = self.make_order()
        _, payment = self.start_demo(order)
        self.client.post(reverse("payments:demo", args=[payment.reference]), {"outcome": "success"})
        payment.refresh_from_db()
        with self.assertRaises(PaymentError):
            refund_payment(payment, payment.amount + 1)
        refund_payment(payment, payment.amount, "Test")
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, Payment.REFUNDED)
        self.assertEqual(order.status, Order.REFUNDED)
        self.assertEqual(order.invoice.status, Invoice.VOID)

    def test_unpaid_cannot_be_refunded(self):
        order = self.make_order()
        _, payment = self.start_demo(order)
        with self.assertRaises(PaymentError):
            refund_payment(payment, Decimal("1"))


class ManualPaymentTests(Base):
    def setUp(self):
        super().setUp()
        PaymentMethodConfig.objects.filter(code="bank_transfer").update(
            is_enabled=True, instructions="Bank: Test Bank\nAccount: 0000")
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "pass12345!")

    def test_bank_transfer_flow_with_staff_confirmation(self):
        order = self.make_order("bdt")
        response = self.client.post(reverse("orders:review", args=[order.number]), {"method": "bank_transfer"})
        payment = order.payments.get()
        self.assertRedirects(response, reverse("payments:instructions", args=[payment.reference]))
        self.assertContains(self.client.get(response["Location"]), "Account: 0000")
        self.assertContains(self.client.get(order.get_absolute_url()), "Payment instructions")

        self.client.force_login(self.admin)
        self.client.post(reverse("admin:payments_payment_changelist"),
                         {"action": "mark_received", "_selected_action": [payment.pk]})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.PAID)

    def test_staff_cannot_hand_mark_online_payments(self):
        order = self.make_order()
        _, payment = self.start_demo(order)
        self.client.force_login(self.admin)
        self.client.post(reverse("admin:payments_payment_changelist"),
                         {"action": "mark_received", "_selected_action": [payment.pk]})
        order.refresh_from_db()
        self.assertNotEqual(order.status, Order.PAID)

    def test_disabled_method_cannot_be_used(self):
        order = self.make_order("usd")
        response = self.client.post(reverse("orders:review", args=[order.number]), {"method": "payoneer_invoice"})
        self.assertEqual(order.payments.count(), 0)
        self.assertRedirects(response, reverse("orders:review", args=[order.number]))


class InvoiceDashboardTests(Base):
    def test_invoice_and_dashboard(self):
        order = self.make_order("usd", [self.addon])
        _, payment = self.start_demo(order)
        self.client.post(reverse("payments:demo", args=[payment.reference]), {"outcome": "success"})
        invoice = Invoice.objects.get(order=order)
        self.assertRegex(invoice.number, r"^INV-\d{4}-0001$")

        page = self.client.get(reverse("orders:invoice", args=[order.number]))
        for text in [invoice.number, order.number, "Jane Client", "Business Website", "Rush delivery",
                     "$ 170", "USD", "Paid", "DEMO"]:
            self.assertContains(page, text)

        dash = self.client.get(reverse("orders:dashboard"))
        for text in ["My Orders", order.number, payment.reference, invoice.number]:
            self.assertContains(dash, text)

    def test_invoice_numbers_are_sequential(self):
        first = Invoice.objects.create(order=self.make_order())
        second = Invoice.objects.create(order=self.make_order())
        self.assertEqual(int(second.number[-4:]), int(first.number[-4:]) + 1)


class QuoteTests(Base):
    def test_quote_request_and_order(self):
        response = self.client.post(reverse("orders:quote"), {
            "service": self.service.pk, "full_name": "Jane Client", "email": "jane@example.com",
            "currency": "usd", "budget": "$3,000", "brief": "A booking website with online payments and admin.",
        })
        self.assertRedirects(response, reverse("orders:dashboard"))
        quote = QuoteRequest.objects.get()
        self.assertEqual(quote.user, self.user)

        quote.quoted_amount = Decimal("2500")
        quote.save()
        order = create_order_from_quote(quote)
        self.assertEqual(order.total, Decimal("2500"))
        self.assertEqual(order.status, Order.PENDING_PAYMENT)
        self.assertTrue(order.is_payable)


class AccountTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_signup_and_login_with_email(self):
        response = self.client.post(reverse("accounts:signup"), {
            "full_name": "New Client", "email": "New@Example.com",
            "password1": "a-Strong-pass-2026", "password2": "a-Strong-pass-2026",
        })
        self.assertRedirects(response, reverse("orders:dashboard"))
        user = User.objects.get(email="new@example.com")
        self.assertEqual(user.username, "new@example.com")
        self.client.logout()
        response = self.client.post(reverse("accounts:login"),
                                    {"username": "new@example.com", "password": "a-Strong-pass-2026"})
        self.assertRedirects(response, reverse("orders:dashboard"))

    def test_duplicate_email_rejected(self):
        User.objects.create_user("a@b.com", "a@b.com", "x")
        response = self.client.post(reverse("accounts:signup"), {
            "full_name": "X", "email": "a@b.com", "password1": "a-Strong-pass-2026", "password2": "a-Strong-pass-2026"})
        self.assertContains(response, "already exists")

    def test_login_and_signup_pages_render(self):
        for name in ("accounts:login", "accounts:signup"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
            self.assertContains(response, "OS Agency")

    def test_navbar_shows_login(self):
        self.assertContains(self.client.get(reverse("home:index")), reverse("accounts:login"))


class AdminTests(Base):
    def test_admin_pages_open(self):
        admin = User.objects.create_superuser("root", "root@example.com", "pass12345!")
        self.client.force_login(admin)
        order = self.make_order()
        _, payment = self.start_demo(order)
        for name, args in [("orders_order_changelist", []), ("orders_order_change", [order.pk]),
                           ("orders_customerprofile_changelist", []), ("orders_invoice_changelist", []),
                           ("payments_payment_changelist", []), ("payments_payment_change", [payment.pk]),
                           ("payments_paymentmethodconfig_changelist", []), ("payments_paymentevent_changelist", []),
                           ("payments_refund_changelist", []), ("service_addon_changelist", []),
                           ("service_quoterequest_changelist", [])]:
            self.assertEqual(self.client.get(reverse(f"admin:{name}", args=args)).status_code, 200, name)


class CouponTests(Base):
    """SAJIDXP comes from migration orders.0003: 15% off, once per customer."""

    def apply(self, order, code, action="apply"):
        return self.client.post(reverse("orders:coupon", args=[order.number]), {"code": code, "action": action})

    def pay_with_demo(self, order):
        _, payment = self.start_demo(order)
        self.client.post(reverse("payments:demo", args=[payment.reference]), {"outcome": "success"})
        return payment

    def test_sajidxp_gives_15_percent_in_both_currencies(self):
        usd = self.make_order("usd", [self.addon])        # 150 + 20 = 170
        self.apply(usd, "sajidxp")                         # not case-sensitive
        usd.refresh_from_db()
        self.assertEqual(usd.coupon_code, "SAJIDXP")
        self.assertEqual(usd.discount, Decimal("25.50"))
        self.assertEqual(usd.total, Decimal("144.50"))

        bdt = self.make_order("bdt")                        # 15,000
        self.apply(bdt, " SAJIDXP ")
        bdt.refresh_from_db()
        self.assertEqual(bdt.total, Decimal("12750.00"))
        review = self.client.get(reverse("orders:review", args=[bdt.number]))
        self.assertContains(review, "SAJIDXP")
        self.assertContains(review, "৳ 12,750")

    def test_paid_amount_includes_discount(self):
        order = self.make_order("usd")
        self.apply(order, "SAJIDXP")
        payment = self.pay_with_demo(order)
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.amount, Decimal("127.50"))
        self.assertEqual(order.status, Order.PAID)
        invoice = self.client.get(reverse("orders:invoice", args=[order.number]))
        self.assertContains(invoice, "Discount (SAJIDXP)")

    def test_once_per_customer(self):
        first = self.make_order()
        self.apply(first, "SAJIDXP")
        self.pay_with_demo(first)

        second = self.make_order()
        response = self.apply(second, "SAJIDXP")
        second.refresh_from_db()
        self.assertEqual(second.discount, 0)
        self.assertContains(self.client.get(response["Location"]), "already used this coupon")

        # Another customer can still use it
        self.client.force_login(self.other)
        other_order = create_order(self.other, self.package, "usd", [], {**CONTACT, "email": "bob@example.com"})
        self.apply(other_order, "SAJIDXP")
        other_order.refresh_from_db()
        self.assertEqual(other_order.coupon_code, "SAJIDXP")

    def test_unpaid_order_does_not_use_up_the_coupon(self):
        abandoned = self.make_order()
        self.apply(abandoned, "SAJIDXP")
        later = self.make_order()
        self.apply(later, "SAJIDXP")
        later.refresh_from_db()
        self.assertEqual(later.coupon_code, "SAJIDXP")

    def test_invalid_expired_inactive(self):
        from datetime import timedelta
        from django.utils import timezone
        from orders.models import Coupon
        order = self.make_order()
        self.apply(order, "NOPE")
        order.refresh_from_db()
        self.assertEqual(order.discount, 0)

        Coupon.objects.create(code="OLD", percent=Decimal("50"), valid_until=timezone.now() - timedelta(days=1))
        Coupon.objects.create(code="OFF", percent=Decimal("50"), is_active=False)
        for code in ("OLD", "OFF"):
            self.apply(order, code)
            order.refresh_from_db()
            self.assertEqual(order.discount, 0, code)

    def test_fixed_coupon_only_in_its_currency(self):
        from orders.models import Coupon
        Coupon.objects.create(code="TAKA500", discount_type=Coupon.FIXED, amount_bdt=Decimal("500"))
        usd = self.make_order("usd")
        self.apply(usd, "TAKA500")
        usd.refresh_from_db()
        self.assertEqual(usd.discount, 0)
        bdt = self.make_order("bdt")
        self.apply(bdt, "TAKA500")
        bdt.refresh_from_db()
        self.assertEqual(bdt.total, Decimal("14500"))

    def test_changing_coupon_cancels_unfinished_payment(self):
        order = self.make_order()
        _, payment = self.start_demo(order)
        self.apply(order, "SAJIDXP")
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.CANCELLED)
        # The old (higher) payment can no longer complete
        self.client.post(reverse("payments:demo", args=[payment.reference]), {"outcome": "success"})
        order.refresh_from_db()
        self.assertNotEqual(order.status, Order.PAID)

    def test_remove_coupon(self):
        order = self.make_order()
        self.apply(order, "SAJIDXP")
        self.apply(order, "", action="remove")
        order.refresh_from_db()
        self.assertEqual((order.coupon_code, order.discount, order.total), ("", 0, Decimal("150")))

    def test_coupon_rechecked_when_paying(self):
        from orders.models import Coupon
        order = self.make_order()
        self.apply(order, "SAJIDXP")
        Coupon.objects.filter(code="SAJIDXP").update(is_active=False)
        response = self.client.post(reverse("orders:review", args=[order.number]), {"method": "demo"})
        self.assertRedirects(response, reverse("orders:review", args=[order.number]))
        self.assertEqual(order.payments.count(), 0)

    def test_other_customer_cannot_touch_coupon(self):
        order = self.make_order()
        self.client.force_login(self.other)
        self.assertEqual(self.apply(order, "SAJIDXP").status_code, 404)


class SandboxCredentialTests(TestCase):
    @override_settings(PAYMENT_MODE="live", SSLCOMMERZ_STORE_ID="testbox", SSLCOMMERZ_STORE_PASSWORD="qwerty",
                       DEBUG=False, SITE_URL="https://osagency.example")
    def test_sandbox_sample_store_is_blocked_in_live_mode(self):
        self.assertIn("payments.E005", [e.id for e in check_payment_settings()])


@override_settings(SSLCOMMERZ_STORE_ID="store_from_env", SSLCOMMERZ_STORE_PASSWORD="secret_from_env")
class AcceptedPaymentLogoTests(Base):
    def footer(self):
        return self.client.get(reverse("home:index")).content.decode()

    def test_only_enabled_methods_show_logos(self):
        html = self.footer()
        self.assertNotIn("We Accept", html)        # only Demo is enabled by default: no real brands

        PaymentMethodConfig.objects.filter(code="sslcommerz").update(is_enabled=True)
        html = self.footer()
        for text in ["We Accept", "International", "Bangladesh", "bKash", "Nagad", "Rocket",
                     "fa-cc-visa", "fa-cc-mastercard"]:
            self.assertIn(text, html)
        self.assertNotIn("Payoneer", html)          # not enabled
        self.assertNotIn("PayPal", html)            # never offered

        PaymentMethodConfig.objects.filter(code="payoneer_invoice").update(is_enabled=True)
        self.assertIn("Payoneer", self.footer())

    @override_settings(SSLCOMMERZ_STORE_ID="", SSLCOMMERZ_STORE_PASSWORD="")
    def test_no_logos_without_credentials(self):
        PaymentMethodConfig.objects.filter(code="sslcommerz").update(is_enabled=True)
        self.assertNotIn("bKash", self.footer())

    def test_uploaded_logo_is_used_and_review_shows_brands(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        import tempfile
        from .models import PaymentBrand
        PaymentMethodConfig.objects.filter(code="sslcommerz").update(is_enabled=True)
        gif = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04"
               b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        with self.settings(MEDIA_ROOT=tempfile.mkdtemp()):
            bkash = PaymentBrand.objects.get(code="bkash")
            bkash.logo = SimpleUploadedFile("bkash.gif", gif, "image/gif")
            bkash.save()
            self.assertIn('alt="bKash"', self.footer())
            order = self.make_order("bdt")
            review = self.client.get(reverse("orders:review", args=[order.number]))
        self.assertContains(review, "pay-brands-inline")
        self.assertContains(review, 'alt="bKash"')
        self.assertContains(review, "Nagad")

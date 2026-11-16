from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import FormView

from core.ratelimit import rate_limit
from home.models import SiteSetting
from payments.models import Payment
from payments.providers import available_methods, get_provider
from payments.services import PaymentError, start_payment
from service.models import CURRENCIES, Package, Service

from .coupons import CouponError, apply_coupon, remove_coupon
from .forms import CheckoutForm, QuoteRequestForm
from .models import Order
from .services import CheckoutError, checkout_addons, create_order, get_profile


def own_order(request, number):
    """Order ownership check: customers only ever see their own orders."""
    order = get_object_or_404(Order.objects.prefetch_related("items", "payments"), number=number)
    if order.user_id != request.user.id and not request.user.is_staff:
        raise Http404
    return order


@method_decorator(login_required, name="dispatch")
@method_decorator(rate_limit("checkout", limit=15, window=60), name="dispatch")
class CheckoutView(View):
    template_name = "orders/checkout.html"

    def get_package(self, package_id):
        package = get_object_or_404(Package.objects.active().select_related("service"), pk=package_id)
        currencies = [c for c in CURRENCIES if package.can_checkout(c)]
        if not currencies:
            raise Http404
        return package, currencies

    def build_form(self, request, package, currencies, data=None):
        profile = get_profile(request.user)
        wanted = request.GET.get("currency")
        currency = wanted if wanted in currencies else (
            profile.preferred_currency if profile.preferred_currency in currencies else currencies[0])
        initial = {
            "currency": currency,
            "full_name": request.user.get_full_name(),
            "email": request.user.email,
            "phone": profile.phone, "company": profile.company, "country": profile.country,
        }
        chosen = (data or {}).get("currency", currency)
        chosen = chosen if chosen in currencies else currency
        form = CheckoutForm(data, initial=initial, available_currencies=currencies,
                            addons_queryset=checkout_addons(package, chosen))
        return form, chosen

    def render_page(self, request, package, currencies, form, currency):
        all_addons = {c: list(checkout_addons(package, c)) for c in currencies}
        return render(request, self.template_name, {
            "package": package, "form": form, "currency": currency, "currencies": currencies,
            "addons_by_currency": all_addons,
        })

    def get(self, request, package_id):
        package, currencies = self.get_package(package_id)
        form, currency = self.build_form(request, package, currencies)
        return self.render_page(request, package, currencies, form, currency)

    def post(self, request, package_id):
        package, currencies = self.get_package(package_id)
        form, currency = self.build_form(request, package, currencies, data=request.POST)
        if form.is_valid():
            try:
                order = create_order(request.user, package, form.cleaned_data["currency"],
                                     list(form.cleaned_data["addons"]), form.cleaned_data)
            except CheckoutError as exc:
                messages.error(request, str(exc))
            else:
                return redirect("orders:review", number=order.number)
        else:
            messages.error(request, "Please fix the highlighted fields.")
        return self.render_page(request, package, currencies, form, currency)


@method_decorator(login_required, name="dispatch")
class OrderReviewView(View):
    """Step: review the order and choose how to pay."""

    def get(self, request, number):
        order = own_order(request, number)
        if not order.is_payable:
            return redirect(order.get_absolute_url())
        return render(request, "orders/review.html",
                      {"order": order, "methods": available_methods(order.currency)})

    def post(self, request, number):
        order = own_order(request, number)
        try:
            payment, result = start_payment(order, request.POST.get("method", ""), request)
        except PaymentError as exc:
            messages.error(request, str(exc))
            return redirect("orders:review", number=order.number)
        if result.redirect_url:
            return redirect(result.redirect_url)
        return redirect("payments:instructions", reference=payment.reference)


@login_required
@require_POST
@rate_limit("coupon", limit=10, window=60)
def order_coupon(request, number):
    """Apply or remove a coupon on the review step."""
    order = own_order(request, number)
    try:
        if request.POST.get("action") == "remove":
            remove_coupon(order)
            messages.info(request, "Coupon removed.")
        else:
            order = apply_coupon(order, request.POST.get("code", ""))
            messages.success(request, f"Coupon {order.coupon_code} applied: you save {order.display_discount}.")
    except CouponError as exc:
        messages.error(request, str(exc))
    return redirect("orders:review", number=order.number)


@login_required
def order_detail(request, number):
    order = own_order(request, number)
    latest = order.payments.first()
    return render(request, "orders/order_detail.html", {
        "order": order,
        "invoice": getattr(order, "invoice", None),
        "latest_payment": latest,
        # Manual methods (bank / Payoneer) show their instructions until staff confirm the money
        "show_instructions": bool(latest and latest.status == Payment.PENDING
                                  and get_provider(latest.provider).is_manual),
    })


@login_required
@require_POST
def order_cancel(request, number):
    order = own_order(request, number)
    if order.status in Order.PAYABLE and not order.payments.filter(status=Payment.SUCCEEDED).exists():
        order.payments.filter(status__in=Payment.OPEN).update(status=Payment.CANCELLED,
                                                              failure_reason="Order cancelled by customer")
        order.status = Order.CANCELLED
        order.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Order {order.number} was cancelled.")
    else:
        messages.error(request, "This order can no longer be cancelled. Please contact us.")
    return redirect(order.get_absolute_url())


@login_required
def invoice_view(request, number):
    order = own_order(request, number)
    invoice = getattr(order, "invoice", None)
    if invoice is None:
        raise Http404
    return render(request, "orders/invoice.html",
                  {"order": order, "invoice": invoice, "site": SiteSetting.load(),
                   "paid_payment": order.payments.filter(status=Payment.SUCCEEDED).first()})


@login_required
def dashboard(request):
    orders = request.user.orders.prefetch_related("items").select_related("invoice")
    payments = Payment.objects.filter(order__user=request.user).select_related("order")[:20]
    return render(request, "orders/dashboard.html", {
        "orders": orders,
        "payments": payments,
        "invoices": [o.invoice for o in orders if hasattr(o, "invoice")],
        "quotes": request.user.quote_requests.select_related("service")[:10],
    })


@method_decorator(rate_limit("quote", limit=5, window=60), name="dispatch")
class QuoteRequestView(FormView):
    template_name = "orders/quote.html"
    form_class = QuoteRequestForm

    def get_initial(self):
        initial = super().get_initial()
        slug = self.request.GET.get("service")
        if slug:
            initial["service"] = Service.objects.active().filter(slug=slug).first()
        if self.request.user.is_authenticated:
            user = self.request.user
            initial.update({"full_name": user.get_full_name(), "email": user.email,
                            "currency": get_profile(user).preferred_currency})
        return initial

    def form_valid(self, form):
        quote = form.save(commit=False)
        if self.request.user.is_authenticated:
            quote.user = self.request.user
        quote.save()
        messages.success(self.request, "Thank you! We received your project brief and will send you a quote.")
        if self.request.user.is_authenticated:
            return redirect("orders:dashboard")
        return redirect("orders:quote")

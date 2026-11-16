import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from core.ratelimit import rate_limit

from .models import Payment, PaymentMethodConfig
from .providers import ProviderError, get_provider
from .providers.demo import OUTCOMES, SIGNATURE_HEADER, build_event, signature_is_valid
from .services import apply_result, record_event

logger = logging.getLogger(__name__)

DEMO_STATUS = {"success": Payment.SUCCEEDED, "failure": Payment.FAILED,
               "cancel": Payment.CANCELLED, "pending": Payment.PENDING}


def own_payment(request, reference):
    """A payment the logged-in customer owns (staff may see all)."""
    payment = get_object_or_404(Payment.objects.select_related("order"), reference=reference)
    if payment.order.user_id != request.user.id and not request.user.is_staff:
        raise Http404
    return payment


# ---------------------------------------------------------------------------
# Demo provider (sandbox only)
# ---------------------------------------------------------------------------

def process_demo_event(body, signature):
    """The demo webhook handler. Used by the HTTP endpoint and the demo page."""
    if not signature_is_valid(body, signature):
        return 400, "invalid signature"
    data = json.loads(body)
    payment = Payment.objects.filter(reference=data.get("reference"), provider="demo").first()
    event, is_new = record_event("demo", data.get("event_id", ""), data, True, payment)
    if not is_new:
        return 200, "duplicate ignored"
    if payment is None or data.get("outcome") not in OUTCOMES:
        event.result = "unknown payment or outcome"
        event.save(update_fields=["result"])
        return 400, event.result
    apply_result(payment, DEMO_STATUS[data["outcome"]], transaction_id=data.get("transaction_id", ""),
                 amount=data.get("amount"), currency=data.get("currency", ""), raw={"demo": True, **data},
                 reason="" if data["outcome"] == "success" else f"Demo {data['outcome']}")
    event.result = f"applied {data['outcome']}"
    event.save(update_fields=["result"])
    return 200, event.result


@csrf_exempt
@rate_limit("webhook-demo", limit=120, window=60)
def demo_webhook(request):
    if settings.PAYMENT_MODE == "live":
        raise Http404
    if request.method != "POST":
        return HttpResponse(status=405)
    status, message = process_demo_event(request.body, request.META.get(SIGNATURE_HEADER, ""))
    return HttpResponse(message, status=status, content_type="text/plain")


@method_decorator(login_required, name="dispatch")
class DemoCheckoutView(View):
    """A fake hosted payment page. Clearly labelled; never charges anything."""

    def dispatch(self, request, *args, **kwargs):
        if settings.PAYMENT_MODE == "live":
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, reference):
        payment = own_payment(request, reference)
        if payment.provider != "demo":
            raise Http404
        return render(request, "payments/demo.html", {"payment": payment, "order": payment.order})

    def post(self, request, reference):
        payment = own_payment(request, reference)
        outcome = request.POST.get("outcome")
        if payment.provider != "demo" or outcome not in OUTCOMES:
            return HttpResponseBadRequest("Unknown demo outcome")
        if payment.status in Payment.OPEN:
            # Simulate the provider calling our webhook (signed, through the same handler).
            body, signature = build_event(payment, outcome)
            process_demo_event(body, signature)
        return redirect(payment.order.get_absolute_url())


# ---------------------------------------------------------------------------
# SSLCOMMERZ
# ---------------------------------------------------------------------------

STATUS_FROM_SSL = {"FAILED": Payment.FAILED, "CANCELLED": Payment.CANCELLED,
                   "UNATTEMPTED": Payment.CANCELLED, "EXPIRED": Payment.FAILED}


def handle_sslcommerz_notification(data):
    """Shared by IPN and return URLs. Trusts nothing until the Validation API confirms it."""
    tran_id = data.get("tran_id", "")
    payment = Payment.objects.filter(reference=tran_id, provider="sslcommerz").first()
    event_id = data.get("val_id") or f"{tran_id}:{data.get('status', '')}"
    safe = {k: v for k, v in data.items() if k not in ("card_no", "card_number")}
    event, is_new = record_event("sslcommerz", event_id, safe, False, payment)
    if payment is None:
        event.result = "unknown tran_id"
        event.save(update_fields=["result"])
        return None
    if not is_new:
        return payment

    status = data.get("status", "")
    provider = get_provider("sslcommerz")
    if status in ("VALID", "VALIDATED") and data.get("val_id"):
        try:
            result = provider.validate(payment, data["val_id"])
        except ProviderError as exc:
            event.result = f"validation call failed: {exc}"
            event.save(update_fields=["result"])
            return payment   # stays pending; a later IPN retry can complete it
        event.signature_valid = result.status == Payment.SUCCEEDED
        apply_result(payment, result.status, transaction_id=result.transaction_id, amount=result.amount,
                     currency=result.currency, raw=result.raw, reason=result.reason)
        event.result = f"validated: {result.status} {result.reason}".strip()
    elif status in STATUS_FROM_SSL:
        apply_result(payment, STATUS_FROM_SSL[status], raw=safe, reason=f"SSLCOMMERZ {status}")
        event.result = f"applied {status}"
    else:
        event.result = f"ignored status {status!r}"
    event.save(update_fields=["result", "signature_valid"])
    return payment


@csrf_exempt
@rate_limit("ipn-sslcommerz", limit=120, window=60)
def sslcommerz_ipn(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    handle_sslcommerz_notification(request.POST.dict())
    return HttpResponse("OK", content_type="text/plain")


@csrf_exempt
def sslcommerz_return(request, outcome):
    """Customer comes back from SSLCOMMERZ. The status is still decided by the Validation API."""
    data = request.POST.dict() if request.method == "POST" else request.GET.dict()
    payment = handle_sslcommerz_notification(data) if data.get("tran_id") else None
    if payment is None:
        return redirect("orders:dashboard")
    return redirect(payment.order.get_absolute_url())


# ---------------------------------------------------------------------------
# Manual methods
# ---------------------------------------------------------------------------

@login_required
def payment_instructions(request, reference):
    payment = own_payment(request, reference)
    config = PaymentMethodConfig.objects.filter(code=payment.provider).first()
    if not config or not get_provider(payment.provider).is_manual:
        raise Http404
    return render(request, "payments/instructions.html",
                  {"payment": payment, "order": payment.order, "config": config})

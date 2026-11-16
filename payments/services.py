"""Payment workflow. All order/payment status changes for payments happen here.

Rules:
- An order becomes Paid only from a provider's server-side confirmation
  (verified webhook / validation API) or a staff confirmation in admin.
  The customer's return page never changes a status.
- Every result is applied inside a transaction with row locks and is idempotent:
  the same webhook twice, or a webhook after the return page, changes nothing.
- Amount and currency must match the order exactly.
"""
import logging
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from orders.coupons import CouponError, check_coupon_before_payment
from orders.models import Invoice, Order
from orders.notifications import send_order_paid_emails

from .models import Payment, PaymentEvent, Refund
from .providers import ProviderError, available_methods, get_provider

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """Shown to the customer as a friendly message."""


def ensure_invoice(order):
    invoice, _ = Invoice.objects.get_or_create(order=order)
    return invoice


def start_payment(order, method_code, request):
    """Create a Payment for the order and hand it to the provider. Returns (payment, StartResult)."""
    methods = {config.code: (config, provider) for config, provider in available_methods(order.currency)}
    if method_code not in methods:
        raise PaymentError("This payment method is not available for this order.")
    config, provider = methods[method_code]

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if not order.is_payable:
            raise PaymentError("This order cannot be paid any more.")
        if order.payments.filter(status=Payment.SUCCEEDED).exists():
            raise PaymentError("This order is already paid.")
        try:
            check_coupon_before_payment(order)
        except CouponError as exc:
            raise PaymentError(f"Coupon {order.coupon_code}: {exc} Please remove it to continue.") from exc

        # One open attempt at a time: older unfinished attempts are closed.
        order.payments.filter(status__in=Payment.OPEN).update(status=Payment.CANCELLED,
                                                              failure_reason="Replaced by a new attempt")
        payment = Payment.objects.create(order=order, provider=method_code, amount=order.total,
                                         currency=order.currency, is_sandbox=provider.is_sandbox(),
                                         status=Payment.PENDING)
        order.status = Order.PENDING_PAYMENT
        order.payment_method = method_code
        order.save(update_fields=["status", "payment_method", "updated_at"])
        ensure_invoice(order)

    try:
        result = provider.start(payment, request)
    except ProviderError as exc:
        logger.warning("Payment start failed for %s: %s", payment.reference, exc)
        apply_result(payment, Payment.FAILED, reason=str(exc))
        raise PaymentError("The payment provider could not start the payment. Please try again.") from exc
    return payment, result


def record_event(provider, event_id, payload, signature_valid, payment=None):
    """Store a webhook delivery once. Returns (event, is_new)."""
    try:
        with transaction.atomic():
            event = PaymentEvent.objects.create(provider=provider, event_id=event_id, payload=payload,
                                                signature_valid=signature_valid, payment=payment)
        return event, True
    except IntegrityError:
        return PaymentEvent.objects.get(provider=provider, event_id=event_id), False


def apply_result(payment, status, *, transaction_id="", amount=None, currency="", raw=None, reason="",
                 confirmed_by_staff=False):
    """Apply a verified outcome to a payment and its order. Safe to call more than once."""
    with transaction.atomic():
        payment = Payment.objects.select_for_update().select_related("order").get(pk=payment.pk)
        order = Order.objects.select_for_update().get(pk=payment.order_id)

        if payment.status in (Payment.SUCCEEDED, Payment.REFUNDED):
            return payment  # final: duplicates and late callbacks change nothing

        if raw:
            payment.raw_response = raw
        if transaction_id:
            payment.provider_transaction_id = transaction_id

        if status == Payment.SUCCEEDED:
            if not confirmed_by_staff:
                if amount is None or Decimal(amount) != payment.amount or currency != payment.currency:
                    status, reason = Payment.FAILED, (
                        f"Amount/currency mismatch: got {amount} {currency}, expected {payment.amount} {payment.currency}")
            if status == Payment.SUCCEEDED and (payment.amount != order.total or payment.currency != order.currency):
                status, reason = Payment.FAILED, "Order total changed after the payment started"

        payment.status = status
        payment.failure_reason = reason[:255]
        if status == Payment.SUCCEEDED:
            payment.verified_at = timezone.now()
        payment.save()

        if status == Payment.SUCCEEDED:
            order.status = Order.PAID
            order.paid_at = timezone.now()
            Invoice.objects.filter(order=order).update(status=Invoice.PAID)
            transaction.on_commit(lambda: send_order_paid_emails(order))
        elif status == Payment.FAILED and order.status != Order.PAID:
            order.status = Order.FAILED
        elif status == Payment.CANCELLED and order.status != Order.PAID:
            order.status = Order.PENDING_PAYMENT   # customer may try again
        elif status == Payment.PENDING and order.status != Order.PAID:
            order.status = Order.PAYMENT_PROCESSING
        order.save(update_fields=["status", "paid_at", "updated_at"])
    return payment


def refund_payment(payment, amount, reason="", user=None):
    """Refund through the provider (or record a manual refund). Returns the Refund."""
    if payment.status != Payment.SUCCEEDED:
        raise PaymentError("Only successful payments can be refunded.")
    amount = Decimal(amount)
    already = sum((r.amount for r in payment.refunds.exclude(status=Refund.FAILED)), Decimal("0"))
    if amount <= 0 or amount + already > payment.amount:
        raise PaymentError("Refund amount is more than what is left to refund.")

    provider = get_provider(payment.provider)
    if provider.is_manual:
        # Money is returned by hand (bank / Payoneer); staff record it here.
        refund = Refund.objects.create(payment=payment, amount=amount, reason=reason, status=Refund.SUCCEEDED,
                                       raw_response={"manual": True}, created_by=user)
    else:
        try:
            result = provider.refund(payment, amount, reason)
        except ProviderError as exc:
            raise PaymentError(str(exc)) from exc
        refund = Refund.objects.create(payment=payment, amount=amount, reason=reason, status=result.status,
                                       provider_refund_id=result.refund_id, raw_response=result.raw,
                                       created_by=user)

    if refund.status == Refund.SUCCEEDED and amount + already == payment.amount:
        with transaction.atomic():
            Payment.objects.filter(pk=payment.pk).update(status=Payment.REFUNDED)
            Order.objects.filter(pk=payment.order_id).update(status=Order.REFUNDED)
            Invoice.objects.filter(order_id=payment.order_id).update(status=Invoice.VOID)
    return refund


def payment_mode():
    return settings.PAYMENT_MODE

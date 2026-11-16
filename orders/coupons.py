"""Coupon rules. The discount is always calculated on the server from the coupon in the database."""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from .models import Coupon, Order


class CouponError(Exception):
    """Shown to the customer."""


def find_coupon(code):
    code = (code or "").strip()
    if not code:
        return None
    return Coupon.objects.filter(code__iexact=code).first()


def _uses(coupon, exclude_order=None, user=None):
    orders = coupon.orders.filter(status__in=Order.COUPON_USED)
    if exclude_order is not None:
        orders = orders.exclude(pk=exclude_order.pk)
    if user is not None:
        orders = orders.filter(user=user)
    return orders.count()


def validate_coupon(coupon, order):
    """Raise CouponError if the coupon cannot be used on this order right now."""
    now = timezone.now()
    if coupon is None or not coupon.is_active:
        raise CouponError("This coupon code is not valid.")
    if coupon.valid_from and now < coupon.valid_from:
        raise CouponError("This coupon is not active yet.")
    if coupon.valid_until and now > coupon.valid_until:
        raise CouponError("This coupon has expired.")
    if coupon.discount_type == Coupon.FIXED and getattr(coupon, f"amount_{order.currency}") is None:
        raise CouponError(f"This coupon cannot be used with {order.currency_code}.")
    minimum = getattr(coupon, f"min_order_{order.currency}")
    if minimum is not None and order.subtotal < minimum:
        raise CouponError(f"This coupon needs an order of at least {order.money(minimum)}.")
    if coupon.max_uses is not None and _uses(coupon, exclude_order=order) >= coupon.max_uses:
        raise CouponError("This coupon has been fully used.")
    if (coupon.max_uses_per_customer is not None
            and _uses(coupon, exclude_order=order, user=order.user) >= coupon.max_uses_per_customer):
        raise CouponError("You have already used this coupon.")


def calculate_discount(coupon, order):
    if coupon.discount_type == Coupon.PERCENT:
        discount = order.subtotal * coupon.percent / Decimal("100")
    else:
        discount = getattr(coupon, f"amount_{order.currency}")
    discount = Decimal(discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return min(discount, order.subtotal)


def _close_open_payments(order):
    # The total changes, so an unfinished payment for the old total must not complete.
    from payments.models import Payment
    order.payments.filter(status__in=Payment.OPEN).update(status=Payment.CANCELLED,
                                                          failure_reason="Order total changed (coupon)")


@transaction.atomic
def apply_coupon(order, code):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in Order.PAYABLE:
        raise CouponError("A coupon can no longer be added to this order.")
    coupon = find_coupon(code)
    if coupon is None:
        raise CouponError("This coupon code is not valid.")
    validate_coupon(coupon, order)
    _close_open_payments(order)
    order.coupon, order.coupon_code = coupon, coupon.code
    order.discount = calculate_discount(coupon, order)
    order.recalculate(save=False)
    order.save(update_fields=["coupon", "coupon_code", "discount", "subtotal", "total", "updated_at"])
    return order


@transaction.atomic
def remove_coupon(order):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in Order.PAYABLE:
        raise CouponError("This order can no longer be changed.")
    _close_open_payments(order)
    order.coupon, order.coupon_code, order.discount = None, "", Decimal("0")
    order.recalculate(save=False)
    order.save(update_fields=["coupon", "coupon_code", "discount", "subtotal", "total", "updated_at"])
    return order


def check_coupon_before_payment(order):
    """A coupon applied earlier must still be valid when the customer pays."""
    if order.coupon_id:
        validate_coupon(order.coupon, order)

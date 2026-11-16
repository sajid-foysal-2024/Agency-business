"""The interface every payment provider adapter implements.

Checkout only talks to this interface, so a new gateway = one new adapter class
registered in providers/__init__.py. Nothing else in checkout changes.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings


class ProviderError(Exception):
    """The provider could not be reached or refused the request."""


@dataclass
class StartResult:
    redirect_url: str = ""      # send the customer here (hosted payment page)
    instructions: str = ""      # or show these (manual methods)


@dataclass
class VerifyResult:
    """What the provider's own server says about a payment."""

    status: str                         # a Payment.STATUS value
    transaction_id: str = ""
    amount: Decimal | None = None
    currency: str = ""                  # "bdt" / "usd"
    raw: dict = field(default_factory=dict)
    reason: str = ""


@dataclass
class RefundResult:
    status: str                         # a Refund.STATUS value
    refund_id: str = ""
    raw: dict = field(default_factory=dict)


class BaseProvider:
    code = ""
    is_manual = False       # True = staff confirms the payment in admin
    supports_refund = False

    @staticmethod
    def is_sandbox():
        return settings.PAYMENT_MODE != "live"

    def is_configured(self):
        """Has everything it needs (credentials, mode) to be offered to customers."""
        return True

    def start(self, payment, request) -> StartResult:
        raise NotImplementedError

    def refund(self, payment, amount, reason) -> RefundResult:
        raise ProviderError("This payment method does not support online refunds.")

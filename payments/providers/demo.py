"""DEMO provider: an internal mock for development and tests.

It never contacts a bank, never moves money and only works in PAYMENT_MODE=sandbox.
Its "webhook" is signed with a key derived from SECRET_KEY, so the real webhook
code path (signature check, duplicate protection, status update) is exercised.
"""
import hashlib
import hmac
import json
import uuid

from django.conf import settings
from django.urls import reverse

from .base import BaseProvider, RefundResult, StartResult

SIGNATURE_HEADER = "HTTP_X_DEMO_SIGNATURE"
OUTCOMES = {"success", "failure", "cancel", "pending"}


def _key():
    return hashlib.sha256(f"demo-webhook:{settings.SECRET_KEY}".encode()).digest()


def sign(body: bytes) -> str:
    return hmac.new(_key(), body, hashlib.sha256).hexdigest()


def signature_is_valid(body: bytes, signature: str) -> bool:
    return bool(signature) and hmac.compare_digest(sign(body), signature)


def build_event(payment, outcome):
    """A webhook body exactly like a real provider would send."""
    body = json.dumps({
        "event_id": f"demo_{uuid.uuid4().hex}",
        "reference": payment.reference,
        "outcome": outcome,
        "amount": str(payment.amount),
        "currency": payment.currency,
        "transaction_id": f"DEMO-{payment.reference[-8:]}",
    }, sort_keys=True).encode()
    return body, sign(body)


class DemoProvider(BaseProvider):
    code = "demo"
    supports_refund = True

    def is_configured(self):
        return self.is_sandbox()   # never available in live mode

    def start(self, payment, request):
        return StartResult(redirect_url=reverse("payments:demo", kwargs={"reference": payment.reference}))

    def refund(self, payment, amount, reason):
        return RefundResult(status="succeeded", refund_id=f"DEMO-REFUND-{uuid.uuid4().hex[:10].upper()}",
                            raw={"demo": True, "amount": str(amount), "reason": reason})

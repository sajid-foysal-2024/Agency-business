"""SSLCOMMERZ adapter (cards, bKash, Nagad, Rocket, internet banking).

Docs: https://developer.sslcommerz.com/doc/v4/
- Session API starts a payment and returns the hosted payment page URL.
- IPN (server to server) and the return URLs tell us something happened.
- A payment is only trusted after the Validation API confirms it, with the
  amount and currency checked against our own record.
Credentials come only from SSLCOMMERZ_STORE_ID / SSLCOMMERZ_STORE_PASSWORD.
"""
import json
from decimal import Decimal, InvalidOperation
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.urls import reverse

from .base import BaseProvider, ProviderError, RefundResult, StartResult, VerifyResult

SANDBOX_BASE = "https://sandbox.sslcommerz.com"
LIVE_BASE = "https://securepay.sslcommerz.com"
TIMEOUT = 30


def http_call(method, url, params):
    """One HTTP call to SSLCOMMERZ. Kept separate so tests can replace it."""
    data = urlencode(params).encode()
    if method == "GET":
        request = Request(f"{url}?{data.decode()}", method="GET")
    else:
        request = Request(url, data=data, method="POST")
    try:
        with urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 (fixed https host)
            return json.loads(response.read().decode())
    except (URLError, ValueError, TimeoutError) as exc:
        raise ProviderError(f"SSLCOMMERZ request failed: {exc}") from exc


def _decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


class SSLCommerzProvider(BaseProvider):
    code = "sslcommerz"
    supports_refund = True

    @property
    def base_url(self):
        return SANDBOX_BASE if self.is_sandbox() else LIVE_BASE

    def _credentials(self):
        return {"store_id": settings.SSLCOMMERZ_STORE_ID, "store_passwd": settings.SSLCOMMERZ_STORE_PASSWORD}

    def is_configured(self):
        return bool(settings.SSLCOMMERZ_STORE_ID and settings.SSLCOMMERZ_STORE_PASSWORD)

    def start(self, payment, request):
        order = payment.order
        site = settings.SITE_URL

        def url(name, **kw):
            return site + reverse(name, kwargs=kw)

        params = {
            **self._credentials(),
            "total_amount": str(payment.amount),
            "currency": payment.currency.upper(),
            "tran_id": payment.reference,
            "success_url": url("payments:sslcommerz_return", outcome="success"),
            "fail_url": url("payments:sslcommerz_return", outcome="fail"),
            "cancel_url": url("payments:sslcommerz_return", outcome="cancel"),
            "ipn_url": url("payments:sslcommerz_ipn"),
            "cus_name": order.full_name,
            "cus_email": order.email,
            "cus_phone": order.phone or "N/A",
            "cus_add1": order.country or "N/A",
            "cus_city": "N/A",
            "cus_country": order.country or "N/A",
            "shipping_method": "NO",
            "product_name": ", ".join(item.name for item in order.items.all())[:255] or order.number,
            "product_category": "Service",
            "product_profile": "non-physical-goods",
            "value_a": order.number,
        }
        data = http_call("POST", f"{self.base_url}/gwprocess/v4/api.php", params)
        if data.get("status") != "SUCCESS" or not data.get("GatewayPageURL"):
            raise ProviderError(data.get("failedreason") or "SSLCOMMERZ did not create a payment session.")
        payment.provider_session = data.get("sessionkey", "")
        payment.save(update_fields=["provider_session", "updated_at"])
        return StartResult(redirect_url=data["GatewayPageURL"])

    def validate(self, payment, val_id) -> VerifyResult:
        """Ask SSLCOMMERZ's Validation API whether this payment really succeeded."""
        data = http_call("GET", f"{self.base_url}/validator/api/validationserverAPI.php",
                         {"val_id": val_id, **self._credentials(), "format": "json"})
        raw = {k: v for k, v in data.items() if k not in ("card_no", "card_number")}  # never keep card data

        if data.get("status") not in ("VALID", "VALIDATED"):
            return VerifyResult(status="failed", raw=raw, reason=f"Validation status {data.get('status')}")
        if data.get("tran_id") != payment.reference:
            return VerifyResult(status="failed", raw=raw, reason="Transaction id does not match")

        # Non-BDT payments are settled in BDT; currency_type/currency_amount hold what the customer paid.
        if payment.currency == "bdt":
            paid_currency, paid_amount = "bdt", _decimal(data.get("amount"))
        else:
            paid_currency = str(data.get("currency_type", "")).lower()
            paid_amount = _decimal(data.get("currency_amount"))

        return VerifyResult(status="succeeded", transaction_id=str(data.get("bank_tran_id", "")),
                            amount=paid_amount, currency=paid_currency, raw=raw)

    def refund(self, payment, amount, reason):
        bank_tran_id = payment.provider_transaction_id
        if not bank_tran_id:
            raise ProviderError("No bank transaction id stored for this payment.")
        data = http_call("GET", f"{self.base_url}/validator/api/merchantTransIDvalidationAPI.php", {
            **self._credentials(),
            "bank_tran_id": bank_tran_id,
            "refund_trans_id": f"RF-{payment.reference}"[:30],
            "refund_amount": str(amount),
            "refund_remarks": (reason or "Refund")[:255],
            "format": "json",
        })
        status = {"success": "pending", "processing": "pending"}.get(str(data.get("status", "")).lower(), "failed")
        return RefundResult(status=status, refund_id=str(data.get("refund_ref_id", "")), raw=data)

"""Manual methods: bank transfer and Payoneer payment request.

The website only records the request and shows instructions. Staff check that
the money arrived and confirm it in the admin ("Mark payment received").
Payoneer payment requests are emailed links sent from your Payoneer account,
not a website checkout, so there is no API call here.
"""
from .base import BaseProvider, StartResult


class ManualProvider(BaseProvider):
    is_manual = True

    def __init__(self, config=None):
        self.config = config

    def start(self, payment, request):
        return StartResult(instructions=self.config.instructions if self.config else "")


class BankTransferProvider(ManualProvider):
    code = "bank_transfer"


class PayoneerInvoiceProvider(ManualProvider):
    code = "payoneer_invoice"

"""Registry of payment provider adapters. Add a new gateway here."""
from .base import ProviderError, RefundResult, StartResult, VerifyResult  # noqa: F401
from .demo import DemoProvider
from .manual import BankTransferProvider, PayoneerInvoiceProvider
from .sslcommerz import SSLCommerzProvider

PROVIDERS = {
    DemoProvider.code: DemoProvider,
    SSLCommerzProvider.code: SSLCommerzProvider,
    BankTransferProvider.code: BankTransferProvider,
    PayoneerInvoiceProvider.code: PayoneerInvoiceProvider,
}


def get_provider(code, config=None):
    cls = PROVIDERS.get(code)
    if cls is None:
        raise ProviderError(f"Unknown payment provider: {code}")
    return cls(config) if cls.is_manual else cls()


def available_methods(currency):
    """Enabled, correctly configured methods that accept this currency, as (config, provider)."""
    from payments.models import PaymentMethodConfig

    methods = []
    for config in PaymentMethodConfig.objects.filter(is_enabled=True, code__in=PROVIDERS):
        provider = get_provider(config.code, config)
        if config.supports(currency) and provider.is_configured():
            methods.append((config, provider))
    return methods

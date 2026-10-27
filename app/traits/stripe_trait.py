import stripe
from typing import Optional, Dict, Any, List, Set
from app.config import settings

# ------------------------------------------------------------------------------
# Stripe Official Currencies Configuration
# Ref: https://docs.stripe.com/currencies
# ------------------------------------------------------------------------------

# Zero-decimal currencies: smallest unit is the base unit (multiplier = 1)
ZERO_DECIMAL_CURRENCIES: Set[str] = {
    "bif",  # Burundian Franc
    "clp",  # Chilean Peso
    "djf",  # Djiboutian Franc
    "gnf",  # Guinean Franc
    "jpy",  # Japanese Yen
    "kmf",  # Comorian Franc
    "krw",  # South Korean Won
    "mga",  # Malagasy Ariary
    "pyg",  # Paraguayan Guaraní
    "rwf",  # Rwandan Franc
    "ugx",  # Ugandan Shilling
    "vnd",  # Vietnamese Đồng
    "vuv",  # Vanuatu Vatu
    "xaf",  # Central African CFA Franc
    "xof",  # West African CFA Franc
    "xpf",  # CFP Franc
}

# Three-decimal currencies: smallest unit is 1/1000th (multiplier = 1000)
THREE_DECIMAL_CURRENCIES: Set[str] = {
    "bhd",  # Bahraini Dinar
    "jod",  # Jordanian Dinar
    "kwd",  # Kuwaiti Dinar
    "omr",  # Omani Rial
    "tnd",  # Tunisian Dinar
}

# All 135+ officially supported Stripe presentment currencies
SUPPORTED_CURRENCIES: Set[str] = {
    "usd", "aed", "afn", "all", "amd", "ang", "aoa", "ars", "aud", "awg",
    "azn", "bam", "bbd", "bdt", "bgn", "bhd", "bif", "bmd", "bnd", "bob",
    "brl", "bsd", "bwp", "byn", "bzd", "cad", "cdf", "chf", "clp", "cny",
    "cop", "crc", "cve", "czk", "djf", "dkk", "dop", "dzd", "egp", "etb",
    "eur", "fjd", "fkp", "gbp", "gel", "gip", "gmd", "gnf", "gtq", "gyd",
    "hkd", "hnl", "hrk", "htg", "huf", "idr", "ils", "inr", "isk", "jmd",
    "jod", "jpy", "kes", "kgs", "khr", "kmf", "krw", "kwd", "kyd", "kzt",
    "lak", "lbp", "lkr", "lrd", "lsl", "mad", "mdl", "mga", "mkd", "mmk",
    "mnt", "mop", "mro", "mru", "mur", "mvr", "mwk", "mxn", "myr", "mzn",
    "nad", "ngn", "nio", "nok", "npr", "nzd", "omr", "pab", "pen", "pgk",
    "php", "pkr", "pln", "pyg", "qar", "ron", "rsd", "rub", "rwf", "sar",
    "sbd", "scr", "sek", "sgd", "shp", "sle", "sll", "sos", "srd", "std",
    "stn", "szl", "thb", "tjs", "tnd", "top", "try", "ttd", "twd", "tzs",
    "uah", "ugx", "uyu", "uzs", "vnd", "vuv", "wst", "xaf", "xcd", "xof",
    "xpf", "yer", "zar", "zmw"
}


class StripeTrait:
    """
    Stripe trait/mixin containing helper functions for common Stripe operations:
    - Currency conversion & validation (supporting all 135+ official Stripe currencies)
    - Customer management
    - Product & Price management
    - Subscription handling
    - Payment method attachments
    - Checkout session creation
    - Webhook event verification
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ensure_stripe_api_key()

    @staticmethod
    def ensure_stripe_api_key(api_key: Optional[str] = None) -> None:
        """
        Ensure Stripe API key is set from settings or provided argument.
        """
        stripe.api_key = api_key or settings.STRIPE_SECRET_KEY

    # --------------------------------------------------------------------------
    # Currency Utilities (All Stripe Supported Currencies)
    # --------------------------------------------------------------------------
    @classmethod
    def is_supported_currency(cls, currency: str) -> bool:
        """
        Check if a given currency code is officially supported by Stripe.
        """
        return currency.lower().strip() in SUPPORTED_CURRENCIES

    @classmethod
    def validate_currency(cls, currency: str) -> str:
        """
        Validate currency against Stripe's 135+ supported currencies.
        Returns the sanitized lowercase code, or raises ValueError if invalid.
        """
        curr = currency.lower().strip()
        if curr not in SUPPORTED_CURRENCIES:
            raise ValueError(
                f"Currency '{currency}' is not officially supported by Stripe. "
                f"Must be one of the 135+ supported ISO currencies."
            )
        return curr

    @classmethod
    def to_stripe_amount(cls, amount: float | int, currency: str) -> int:
        """
        Convert a human decimal amount to Stripe's integer smallest-unit representation
        according to official Stripe rules:

        1. Zero-decimal currencies (JPY, KRW, VND, CLP, etc.):
           No fractional unit. Multiplier = 1 (e.g. 500 JPY -> 500)
        2. Three-decimal currencies (BHD, JOD, KWD, OMR, TND):
           Smallest unit is 1/1000th. Multiplier = 1000 (e.g. 1.500 KWD -> 1500)
        3. Special case - ISK (Icelandic Króna):
           Must be a multiple of 100 (e.g. 5 ISK -> 500)
        4. Standard two-decimal currencies (USD, EUR, GBP, INR, CAD, AUD, etc.):
           Smallest unit is cents/paise/hundredths. Multiplier = 100 (e.g. 10.50 USD -> 1050)
        """
        curr = cls.validate_currency(currency)

        if curr in ZERO_DECIMAL_CURRENCIES:
            return int(round(amount))
        elif curr in THREE_DECIMAL_CURRENCIES:
            return int(round(amount * 1000))
        elif curr == "isk":
            return int(round(amount)) * 100
        else:
            return int(round(amount * 100))

    @classmethod
    def from_stripe_amount(cls, unit_amount: int, currency: str) -> float:
        """
        Convert Stripe's integer smallest-unit representation back to standard human decimal amount.
        """
        curr = cls.validate_currency(currency)

        if curr in ZERO_DECIMAL_CURRENCIES:
            return float(unit_amount)
        elif curr in THREE_DECIMAL_CURRENCIES:
            return round(unit_amount / 1000.0, 3)
        elif curr == "isk":
            return float(unit_amount // 100)
        else:
            return round(unit_amount / 100.0, 2)

    # --------------------------------------------------------------------------
    # 1. Customer Operations
    # --------------------------------------------------------------------------
    def createCustomer(
        self,
        email: str,
        name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> stripe.Customer:
        """
        Create a new Stripe Customer.
        Equivalent to: createCustomer(string $email, ?string $name = null, array $params = [])
        """
        self.ensure_stripe_api_key()

        payload: Dict[str, Any] = {"email": email}
        if name:
            payload["name"] = name
        if params:
            payload.update(params)

        return stripe.Customer.create(**payload)

    def retrieveCustomer(self, customerId: str) -> stripe.Customer:
        """
        Retrieve a Stripe customer by customerId.
        """
        self.ensure_stripe_api_key()
        return stripe.Customer.retrieve(customerId)

    def updateCustomer(
        self,
        customerId: str,
        params: Dict[str, Any]
    ) -> stripe.Customer:
        """
        Update an existing Stripe customer.
        """
        self.ensure_stripe_api_key()
        return stripe.Customer.modify(customerId, **params)

    # --------------------------------------------------------------------------
    # Stripe Connected Account Operations
    # --------------------------------------------------------------------------
    def createAccount(
        self,
        email: str,
        accountType: str = "express",
        businessType: Optional[str] = "individual",
        metadata: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> stripe.Account:
        """
        Create a new Stripe Connected Account (acc_id).
        """
        self.ensure_stripe_api_key()

        payload: Dict[str, Any] = {
            "type": accountType,
            "email": email,
        }
        if businessType:
            payload["business_type"] = businessType
        if metadata:
            payload["metadata"] = metadata
        if params:
            payload.update(params)

        return stripe.Account.create(**payload)

    def retrieveAccount(self, accountId: str) -> stripe.Account:
        """
        Retrieve a Stripe connected account by accountId.
        """
        self.ensure_stripe_api_key()
        return stripe.Account.retrieve(accountId)

    def getAccountId(self) -> Optional[str]:
        """
        Retrieve the main Stripe account ID associated with the API key.
        """
        self.ensure_stripe_api_key()
        try:
            account = stripe.Account.retrieve()
            return account.id
        except Exception:
            return None

    def updateAccount(
        self,
        accountId: str,
        params: Dict[str, Any]
    ) -> stripe.Account:
        """
        Update an existing Stripe connected account.
        """
        self.ensure_stripe_api_key()
        return stripe.Account.modify(accountId, **params)

    # --------------------------------------------------------------------------
    # 2. Product & Price Operations
    # --------------------------------------------------------------------------
    def createStripeProduct(
        self,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> stripe.Product:
        """
        Create a standalone Stripe product.
        """
        self.ensure_stripe_api_key()

        payload: Dict[str, Any] = {"name": name}
        if description:
            payload["description"] = description
        if metadata:
            payload["metadata"] = metadata
        if params:
            payload.update(params)

        return stripe.Product.create(**payload)

    def updateStripeProduct(
        self,
        productId: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> stripe.Product:
        """
        Update an existing Stripe product.
        """
        self.ensure_stripe_api_key()

        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if metadata is not None:
            payload["metadata"] = metadata
        if params:
            payload.update(params)

        return stripe.Product.modify(productId, **payload)

    def archiveStripePrice(self, priceId: str) -> stripe.Price:
        """
        Archive/deactivate an old Stripe price.
        """
        self.ensure_stripe_api_key()
        return stripe.Price.modify(priceId, active=False)

    def createStripePrice(
        self,
        name: str,
        amount: float,
        currency: str,
        interval: str,
        intervalCount: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
        productId: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> stripe.Price:
        """
        Create a recurring Stripe Price supporting all 135+ official currencies.
        Properly handles zero-decimal, three-decimal, and standard two-decimal amounts.
        If productId is not provided, inline product_data will be created with `name`.
        Equivalent to: createStripePrice(string $name, float $amount, string $currency, string $interval, int $intervalCount = 1, array $metadata = [])
        """
        self.ensure_stripe_api_key()

        # Validate currency & convert amount according to official Stripe rules
        valid_currency = self.validate_currency(currency)
        unit_amount = self.to_stripe_amount(amount, valid_currency)

        price_payload: Dict[str, Any] = {
            "unit_amount": unit_amount,
            "currency": valid_currency,
            "recurring": {
                "interval": interval,
                "interval_count": intervalCount,
            },
        }

        if productId:
            price_payload["product"] = productId
        else:
            product_data: Dict[str, Any] = {"name": name}
            if metadata:
                product_data["metadata"] = metadata
            price_payload["product_data"] = product_data

        if metadata:
            price_payload["metadata"] = metadata

        if params:
            price_payload.update(params)

        return stripe.Price.create(**price_payload)

    # --------------------------------------------------------------------------
    # 3. Payment Method Operations
    # --------------------------------------------------------------------------
    def attachPaymentMethodToCustomer(
        self,
        customerId: str,
        paymentMethodId: str,
        setAsDefault: bool = True
    ) -> stripe.PaymentMethod:
        """
        Attach a payment method to a customer and optionally set it as default.
        Equivalent to: attachPaymentMethodToCustomer(string $customerId, string $paymentMethodId)
        """
        self.ensure_stripe_api_key()

        # Attach payment method to customer
        payment_method = stripe.PaymentMethod.attach(
            paymentMethodId,
            customer=customerId
        )

        # Set as default payment method for invoices/subscriptions
        if setAsDefault:
            stripe.Customer.modify(
                customerId,
                invoice_settings={"default_payment_method": paymentMethodId}
            )

        return payment_method

    def detachPaymentMethod(self, paymentMethodId: str) -> stripe.PaymentMethod:
        """
        Detach a payment method from a customer.
        """
        self.ensure_stripe_api_key()
        return stripe.PaymentMethod.detach(paymentMethodId)

    # --------------------------------------------------------------------------
    # 4. Subscription Operations
    # --------------------------------------------------------------------------
    def createSubscription(
        self,
        customerId: str,
        priceId: str,
        params: Optional[Dict[str, Any]] = None
    ) -> stripe.Subscription:
        """
        Create a subscription for a customer with a given price.
        Equivalent to: createSubscription(string $customerId, string $priceId, array $params = [])
        """
        self.ensure_stripe_api_key()

        payload: Dict[str, Any] = {
            "customer": customerId,
            "items": [{"price": priceId}],
            "payment_behavior": "default_incomplete",
            "payment_settings": {"save_default_payment_method": "on_subscription"},
            "expand": ["latest_invoice.payment_intent"],
        }
        if params:
            payload.update(params)

        return stripe.Subscription.create(**payload)

    def retrieveSubscription(self, subscriptionId: str) -> stripe.Subscription:
        """
        Retrieve a subscription by ID.
        """
        self.ensure_stripe_api_key()
        return stripe.Subscription.retrieve(subscriptionId)

    def cancelSubscription(
        self,
        subscriptionId: str,
        cancelAtPeriodEnd: bool = False,
        params: Optional[Dict[str, Any]] = None
    ) -> stripe.Subscription:
        """
        Cancel a subscription immediately or at period end.
        Equivalent to: cancelSubscription(string $subscriptionId)
        """
        self.ensure_stripe_api_key()

        extra_params = params or {}
        if cancelAtPeriodEnd:
            return stripe.Subscription.modify(
                subscriptionId,
                cancel_at_period_end=True,
                **extra_params
            )

        return stripe.Subscription.cancel(subscriptionId, **extra_params)

    # --------------------------------------------------------------------------
    # 5. Checkout & Billing Portal Sessions
    # --------------------------------------------------------------------------
    def createCheckoutSession(
        self,
        customerId: str,
        priceId: str,
        successUrl: str,
        cancelUrl: str,
        metadata: Optional[Dict[str, Any]] = None,
        subscriptionData: Optional[Dict[str, Any]] = None,
        mode: str = "subscription",
        params: Optional[Dict[str, Any]] = None
    ) -> stripe.checkout.Session:
        """
        Create a Stripe Checkout Session for a subscription.
        Equivalent to: createCheckoutSession(string $customerId, string $priceId, string $successUrl, string $cancelUrl, array $metadata = [], array $subscriptionData = [])
        """
        self.ensure_stripe_api_key()

        session_payload: Dict[str, Any] = {
            "customer": customerId,
            "mode": mode,
            "line_items": [
                {
                    "price": priceId,
                    "quantity": 1,
                }
            ],
            "success_url": successUrl,
            "cancel_url": cancelUrl,
        }

        if metadata:
            session_payload["metadata"] = metadata

        if subscriptionData:
            session_payload["subscription_data"] = subscriptionData

        if params:
            session_payload.update(params)

        return stripe.checkout.Session.create(**session_payload)

    def createCustomerPortalSession(
        self,
        customerId: str,
        returnUrl: str,
        params: Optional[Dict[str, Any]] = None
    ) -> stripe.billing_portal.Session:
        """
        Create a Stripe Customer Billing Portal Session for managing subscriptions & cards.
        """
        self.ensure_stripe_api_key()

        payload: Dict[str, Any] = {
            "customer": customerId,
            "return_url": returnUrl,
        }
        if params:
            payload.update(params)

        return stripe.billing_portal.Session.create(**payload)

    # --------------------------------------------------------------------------
    # 6. Webhooks
    # --------------------------------------------------------------------------
    def constructWebhookEvent(
        self,
        payload: bytes | str,
        sigHeader: str,
        webhookSecret: Optional[str] = None
    ) -> stripe.Event:
        """
        Verify and construct a Stripe Webhook Event from raw payload and signature.
        """
        secret = webhookSecret or settings.STRIPE_WEBHOOK_SECRET
        return stripe.Webhook.construct_event(payload, sigHeader, secret)

    # --------------------------------------------------------------------------
    # Snake_case aliases for Python PEP-8 idiomatic usage
    # --------------------------------------------------------------------------
    create_customer = createCustomer
    retrieve_customer = retrieveCustomer
    update_customer = updateCustomer
    create_account = createAccount
    retrieve_account = retrieveAccount
    update_account = updateAccount
    get_account_id = getAccountId
    create_stripe_product = createStripeProduct
    update_stripe_product = updateStripeProduct
    create_stripe_price = createStripePrice
    archive_stripe_price = archiveStripePrice
    attach_payment_method_to_customer = attachPaymentMethodToCustomer
    detach_payment_method = detachPaymentMethod
    create_subscription = createSubscription
    retrieve_subscription = retrieveSubscription
    cancel_subscription = cancelSubscription
    create_checkout_session = createCheckoutSession
    create_customer_portal_session = createCustomerPortalSession
    construct_webhook_event = constructWebhookEvent

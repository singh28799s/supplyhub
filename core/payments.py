import hashlib
import hmac
from decimal import Decimal, ROUND_HALF_UP

import requests
from django.conf import settings

RAZORPAY_API_URL = "https://api.razorpay.com/v1"


class PaymentGatewayError(Exception):
    ambiguous = False


class PaymentGatewayAmbiguousError(PaymentGatewayError):
    ambiguous = True


def razorpay_is_configured() -> bool:
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def _request(method: str, path: str, *, json=None):
    if not razorpay_is_configured():
        raise PaymentGatewayError("Razorpay API keys are not configured.")
    try:
        response = requests.request(
            method,
            f"{RAZORPAY_API_URL}{path}",
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            json=json,
            timeout=15,
        )
    except requests.RequestException as exc:
        raise PaymentGatewayAmbiguousError(
            "Razorpay request outcome is unknown. Check the Razorpay dashboard before retrying."
        ) from exc
    if not response.ok:
        error = (
            PaymentGatewayAmbiguousError
            if response.status_code >= 500
            else PaymentGatewayError
        )
        raise error(f"Razorpay returned HTTP {response.status_code}.")
    try:
        return response.json()
    except requests.JSONDecodeError as exc:
        raise PaymentGatewayAmbiguousError(
            "Razorpay returned an invalid response; reconcile the request before retrying."
        ) from exc


def create_provider_order(amount: Decimal, receipt: str) -> str:
    amount_paise = int(
        (amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    response = _request(
        "POST",
        "/orders",
        json={
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt[:40],
            "notes": {"supplyhub_order": receipt},
        },
    )
    provider_order_id = response.get("id")
    if not provider_order_id:
        raise PaymentGatewayError("Razorpay did not return an order identifier.")
    return provider_order_id


def verify_checkout_signature(provider_order_id: str, payment_id: str, signature: str) -> bool:
    if not razorpay_is_configured() or not signature:
        return False
    message = f"{provider_order_id}|{payment_id}".encode()
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        message,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def fetch_payment(payment_id: str) -> dict:
    return _request("GET", f"/payments/{payment_id}")


def create_seller_transfer(
    payment_id: str,
    *,
    linked_account_id: str,
    amount_paise: int,
    reference: str,
    seller_order_id: int,
) -> dict:
    response = _request(
        "POST",
        f"/payments/{payment_id}/transfers",
        json={
            "transfers": [
                {
                    "account": linked_account_id,
                    "amount": amount_paise,
                    "currency": "INR",
                    "notes": {
                        "supplyhub_order": reference,
                        "supplyhub_seller_order": str(seller_order_id),
                    },
                    "on_hold": False,
                }
            ]
        },
    )
    transfers = response.get("items", response.get("transfers", []))
    if not transfers and response.get("id"):
        transfers = [response]
    if not transfers or not transfers[0].get("id"):
        raise PaymentGatewayAmbiguousError(
            "Razorpay did not return a transfer ID. Reconcile in Razorpay before retrying."
        )
    return transfers[0]

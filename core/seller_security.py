import logging
import re
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.core.signing import TimestampSigner
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)
EMAIL_VERIFICATION_SALT = "supplyhub.seller-email-verification"
EMAIL_VERIFICATION_WINDOW = 60 * 60
EMAIL_VERIFICATION_MAX_SENDS = 5
EMAIL_VERIFICATION_COOLDOWN = 60


class SellerSecurityError(Exception):
    pass


def normalize_seller_phone(phone, country):
    normalized = re.sub(r"[\s().-]", "", phone or "")
    if normalized.startswith("00"):
        normalized = f"+{normalized[2:]}"
    if normalized.startswith("+"):
        return normalized if re.fullmatch(r"\+[1-9]\d{7,14}", normalized) else ""
    if country.casefold() == "india":
        digits = re.sub(r"\D", "", normalized)
        if len(digits) == 10:
            return f"+91{digits}"
        if len(digits) == 11 and digits.startswith("0"):
            return f"+91{digits[1:]}"
    return ""


def _twilio_verify_request(endpoint, data):
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    service_sid = settings.TWILIO_VERIFY_SERVICE_SID
    if not all((account_sid, auth_token, service_sid)):
        raise SellerSecurityError("Seller SMS verification is not configured yet.")

    url = (
        f"https://verify.twilio.com/v2/Services/"
        f"{quote(service_sid, safe='')}/{endpoint}"
    )
    try:
        response = requests.post(
            url,
            data=data,
            auth=(account_sid, auth_token),
            timeout=(3, 10),
        )
    except requests.RequestException as exc:
        logger.warning("Twilio Verify request failed: %s", exc.__class__.__name__)
        raise SellerSecurityError("SMS verification is temporarily unavailable.") from exc

    try:
        result = response.json()
    except ValueError as exc:
        logger.warning("Twilio Verify returned a non-JSON response.")
        raise SellerSecurityError("SMS verification is temporarily unavailable.") from exc

    if not response.ok:
        logger.warning("Twilio Verify returned HTTP %s.", response.status_code)
        raise SellerSecurityError("SMS verification could not be completed.")
    return result


def send_seller_sms_verification(phone):
    result = _twilio_verify_request(
        "Verifications",
        {"To": phone, "Channel": "sms"},
    )
    if result.get("status") != "pending":
        raise SellerSecurityError("Twilio did not accept the verification request.")


def check_seller_sms_verification(phone, code):
    result = _twilio_verify_request(
        "VerificationCheck",
        {"To": phone, "Code": code},
    )
    return result.get("status") == "approved"


def send_seller_email_verification(request, profile):
    from .models import SellerProfile

    with transaction.atomic():
        locked_profile = SellerProfile.objects.select_for_update().get(pk=profile.pk)
        now = timezone.now()
        window_started = locked_profile.email_verification_window_started_at
        send_count = locked_profile.email_verification_send_count
        if not window_started or (now - window_started).total_seconds() >= EMAIL_VERIFICATION_WINDOW:
            window_started = now
            send_count = 0
        if send_count >= EMAIL_VERIFICATION_MAX_SENDS:
            raise SellerSecurityError(
                "Too many verification emails were requested. Try again in an hour."
            )
        sent_at = locked_profile.email_verification_sent_at
        if sent_at and (now - sent_at).total_seconds() < EMAIL_VERIFICATION_COOLDOWN:
            raise SellerSecurityError(
                "Please wait one minute before requesting another verification email."
            )

        token = TimestampSigner(salt=EMAIL_VERIFICATION_SALT).sign(
            f"{locked_profile.pk}:{locked_profile.email.casefold()}"
        )
        verification_url = request.build_absolute_uri(
            reverse("seller_email_verify", kwargs={"token": token})
        )
        subject = "Verify your SupplyHub seller email"
        message = (
            f"Hello {locked_profile.contact_name},\n\n"
            "Confirm this email address for your SupplyHub seller account by opening "
            f"this link:\n{verification_url}\n\n"
            "For your protection, the link expires after 24 hours. If you did not "
            "request this, you can ignore this message."
        )
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [locked_profile.email],
            fail_silently=False,
        )
        locked_profile.email_verification_window_started_at = window_started
        locked_profile.email_verification_send_count = send_count + 1
        locked_profile.email_verification_sent_at = now
        locked_profile.save(
            update_fields=[
                "email_verification_window_started_at",
                "email_verification_send_count",
                "email_verification_sent_at",
                "updated_at",
            ]
        )

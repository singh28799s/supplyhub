import logging
import re
import secrets
from datetime import timedelta
from urllib.parse import quote

import requests
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)
EMAIL_VERIFICATION_SALT = "supplyhub.seller-email-verification"
EMAIL_VERIFICATION_WINDOW = 60 * 60
EMAIL_VERIFICATION_MAX_SENDS = 5
EMAIL_VERIFICATION_COOLDOWN = 60
EMAIL_VERIFICATION_CODE_TTL = 10 * 60
EMAIL_VERIFICATION_CODE_MAX_ATTEMPTS = 5


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

    if (
        settings.DJANGO_ENV == "production"
        and settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"
    ):
        raise SellerSecurityError(
            "Production email is set to console mode. Configure SMTP in Render first."
        )
    if settings.DJANGO_ENV == "production" and not all(
        (
            settings.EMAIL_HOST,
            settings.EMAIL_HOST_USER,
            settings.EMAIL_HOST_PASSWORD,
        )
    ):
        raise SellerSecurityError(
            "Production SMTP is incomplete. Set EMAIL_HOST, EMAIL_HOST_USER, "
            "and EMAIL_HOST_PASSWORD in Render."
        )

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

        verification_code = f"{secrets.randbelow(900_000) + 100_000:06d}"
        subject = "Verify your SupplyHub seller email"
        message = (
            f"Hello {locked_profile.contact_name},\n\n"
            "Your SupplyHub seller email verification code is:\n\n"
            f"{verification_code}\n\n"
            "This code expires in 10 minutes and can be used once. "
            "If you did not request it, you can ignore this message."
        )
        sent_count = send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [locked_profile.email],
            fail_silently=False,
        )
        if sent_count != 1:
            raise SellerSecurityError("The verification email was not accepted for delivery.")
        locked_profile.email_verification_code_hash = make_password(
            verification_code
        )
        locked_profile.email_verification_code_expires_at = (
            now + timedelta(seconds=EMAIL_VERIFICATION_CODE_TTL)
        )
        locked_profile.email_verification_code_attempts = 0
        locked_profile.email_verification_window_started_at = window_started
        locked_profile.email_verification_send_count = send_count + 1
        locked_profile.email_verification_sent_at = now
        locked_profile.save(
            update_fields=[
                "email_verification_code_hash",
                "email_verification_code_expires_at",
                "email_verification_code_attempts",
                "email_verification_window_started_at",
                "email_verification_send_count",
                "email_verification_sent_at",
                "updated_at",
            ]
        )


def check_seller_email_verification_code(code, encoded_code):
    return bool(encoded_code) and check_password(code, encoded_code)

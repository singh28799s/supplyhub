from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Order, PaymentTransaction, SellerPayout
from .payments import PaymentGatewayError, create_seller_transfer


class PayoutNotReadyError(Exception):
    pass


def release_seller_payout(payout_id: int) -> str:
    now = timezone.now()
    with transaction.atomic():
        payout = (
            SellerPayout.objects.select_for_update()
            .select_related(
                "seller_order__seller",
                "seller_order__order",
            )
            .get(pk=payout_id)
        )
        seller_order = payout.seller_order
        if seller_order.order.status == Order.Status.CANCELLED:
            raise PayoutNotReadyError("Cancelled orders cannot release seller payouts.")
        if not seller_order.delivered_at:
            raise PayoutNotReadyError("Delivery has not been confirmed by Delhivery.")
        eligible_at = seller_order.delivered_at + timedelta(
            days=settings.SUPPLYHUB_PAYOUT_HOLD_DAYS
        )
        if now < eligible_at:
            raise PayoutNotReadyError(
                f"This payout is held until {eligible_at:%Y-%m-%d %H:%M %Z}."
            )
        if not seller_order.seller.razorpay_linked_account_id:
            raise PayoutNotReadyError(
                "Add this seller's verified Razorpay linked-account ID in the seller profile."
            )
        payment = PaymentTransaction.objects.filter(
            order=seller_order.order,
            status=PaymentTransaction.Status.CAPTURED,
            provider_payment_id__isnull=False,
        ).first()
        if payment is None:
            raise PayoutNotReadyError("A captured Razorpay payment is required for seller payout.")
        if payout.razorpay_transfer_id or payout.status == SellerPayout.Status.PROCESSING:
            raise PayoutNotReadyError(
                "A transfer is already in progress or submitted. Reconcile it in Razorpay before retrying."
            )
        if payout.status == SellerPayout.Status.PAID:
            raise PayoutNotReadyError("This payout has already been transferred.")

        payout.status = SellerPayout.Status.PROCESSING
        payout.available_at = eligible_at
        payout.failure_reason = ""
        payout.save(
            update_fields=["status", "available_at", "failure_reason", "updated_at"]
        )
        linked_account_id = seller_order.seller.razorpay_linked_account_id
        amount_paise = int(
            (payout.net_amount * Decimal("100")).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )
        payment_id = payment.provider_payment_id
        reference = str(seller_order.order.reference)

    try:
        transfer = create_seller_transfer(
            payment_id,
            linked_account_id=linked_account_id,
            amount_paise=amount_paise,
            reference=reference,
            seller_order_id=seller_order.pk,
        )
    except PaymentGatewayError as exc:
        # Keep the payout locked as processing: a network failure can happen after
        # Razorpay accepted the transfer, so an automatic retry could pay twice.
        if not exc.ambiguous:
            SellerPayout.objects.filter(
                pk=payout_id,
                status=SellerPayout.Status.PROCESSING,
                razorpay_transfer_id__isnull=True,
            ).update(
                status=SellerPayout.Status.FAILED,
                failure_reason=str(exc),
                updated_at=timezone.now(),
            )
        raise

    with transaction.atomic():
        payout = SellerPayout.objects.select_for_update().get(pk=payout_id)
        payout.razorpay_transfer_id = transfer["id"]
        payout.save(update_fields=["razorpay_transfer_id", "updated_at"])
    return transfer["id"]

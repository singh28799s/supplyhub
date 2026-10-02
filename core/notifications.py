import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from .models import Order, QuoteRequest, StoreSettings

logger = logging.getLogger(__name__)


def _admin_recipients():
    recipients = []
    configured_email = getattr(settings, "SUPPLYHUB_ADMIN_EMAIL", "")
    if configured_email:
        recipients.append(configured_email)
    store_email = StoreSettings.load().support_email
    if store_email and store_email not in recipients:
        recipients.append(store_email)
    return recipients


def _send(subject, body, recipients):
    recipients = list(dict.fromkeys(email for email in recipients if email))
    if not recipients:
        return
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception:
        logger.exception("SupplyHub notification email failed: %s", subject)


def notify_order_created(order_id):
    def send():
        try:
            order = Order.objects.prefetch_related("items").get(pk=order_id)
            store = StoreSettings.load()
            item_lines = [
                f"- {item.product_name}: {item.quantity} {item.unit} x ₹{item.unit_price}"
                for item in order.items.all()
            ]
            body = "\n".join(
                [
                    f"Order reference: {order.reference}",
                    f"Customer: {order.customer_name}",
                    f"Email: {order.email}",
                    f"Phone: {order.phone}",
                    "Items:",
                    *item_lines,
                    f"Shipping: ₹{order.shipping_charge}",
                    f"Total: ₹{order.total_amount}",
                    f"Payment method: {order.get_payment_method_display()}",
                    "Status: Pending confirmation",
                ]
            )
            _send(f"SupplyHub order received: {order.reference}", body, [order.email])
            _send(
                f"New SupplyHub order: {order.reference}",
                body,
                _admin_recipients() or [store.support_email],
            )
        except Order.DoesNotExist:
            logger.warning("Order %s disappeared before its notification was sent.", order_id)

    transaction.on_commit(send)


def notify_order_updated(order_id, changed_fields):
    changed = ", ".join(changed_fields)

    def send():
        try:
            order = Order.objects.get(pk=order_id)
            body = "\n".join(
                [
                    f"Hello {order.customer_name},",
                    f"Your SupplyHub order {order.reference} has been updated.",
                    f"Status: {order.get_status_display()}",
                    f"Payment received: {'Yes' if order.payment_received else 'No'}",
                    f"Total: ₹{order.total_amount}",
                ]
            )
            _send(f"SupplyHub order update: {order.reference}", body, [order.email])
            logger.info("Order %s notification sent after changes: %s", order.reference, changed)
        except Order.DoesNotExist:
            logger.warning("Order %s disappeared before its update notification was sent.", order_id)

    transaction.on_commit(send)


def notify_quote_created(quote_id):
    def send():
        try:
            quote = QuoteRequest.objects.get(pk=quote_id)
            store = StoreSettings.load()
            body = "\n".join(
                [
                    f"Quote request reference: {quote.reference}",
                    f"Customer: {quote.customer_name}",
                    f"Business: {quote.business_name or 'Not provided'}",
                    f"Product: {quote.product_name}",
                    f"Quantity: {quote.quantity}",
                    f"Email: {quote.email}",
                    f"Phone: {quote.phone}",
                    f"Requirements: {quote.message or 'None provided'}",
                ]
            )
            _send(
                f"SupplyHub quote request received: {quote.reference}",
                "Thank you. Your quote request is saved. Our team will contact you.\n\n" + body,
                [quote.email],
            )
            _send(
                f"New SupplyHub quote request: {quote.reference}",
                body,
                _admin_recipients() or [store.support_email],
            )
        except QuoteRequest.DoesNotExist:
            logger.warning("Quote request %s disappeared before its notification was sent.", quote_id)

    transaction.on_commit(send)


def notify_quote_updated(quote_id, changed_fields):
    changed = ", ".join(changed_fields)

    def send():
        try:
            quote = QuoteRequest.objects.get(pk=quote_id)
            body = "\n".join(
                [
                    f"Hello {quote.customer_name},",
                    f"Your quote request {quote.reference} has been updated.",
                    f"Product: {quote.product_name}",
                    f"Quantity: {quote.quantity}",
                    f"Status: {quote.get_status_display()}",
                    f"Quoted unit price: ₹{quote.quoted_unit_price}" if quote.quoted_unit_price is not None else "",
                    f"Seller response: {quote.admin_response or 'No additional message'}",
                ]
            )
            _send(f"SupplyHub quote update: {quote.reference}", body, [quote.email])
            logger.info("Quote %s notification sent after changes: %s", quote.reference, changed)
        except QuoteRequest.DoesNotExist:
            logger.warning("Quote request %s disappeared before its update notification was sent.", quote_id)

    transaction.on_commit(send)

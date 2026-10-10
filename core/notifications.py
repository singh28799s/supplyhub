import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from .models import Order, QuoteRequest, SellerOrder, StoreSettings

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
                    f"Order ID: #{order.pk}",
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
            _send(f"SupplyHub order received: #{order.pk}", body, [order.email])
            _send(
                f"New SupplyHub order: #{order.pk}",
                body,
                _admin_recipients() or [store.support_email],
            )
            seller_orders = order.seller_orders.select_related("seller").prefetch_related("items")
            for seller_order in seller_orders:
                seller_items = [
                    f"- {item.product_name}: {item.quantity} {item.unit} x ₹{item.unit_price}"
                    for item in seller_order.items.all()
                ]
                seller_body = "\n".join(
                    [
                        f"Order ID: #{order.pk}",
                        f"Seller: {seller_order.seller.company_name}",
                        f"Customer: {order.customer_name}",
                        f"Email: {order.email}",
                        f"Phone: {order.phone}",
                        f"Delivery: {order.delivery_address}, {order.city} {order.postal_code}",
                        "Your items:",
                        *seller_items,
                        f"Seller status: {seller_order.get_status_display()}",
                    ]
                )
                _send(
                    f"New SupplyHub order for {seller_order.seller.company_name}: #{order.pk}",
                    seller_body,
                    [seller_order.seller.email],
                )
        except Order.DoesNotExist:
            logger.warning("Order %s disappeared before its notification was sent.", order_id)

    transaction.on_commit(send)


def notify_seller_order_updated(seller_order_id):
    def send():
        try:
            seller_order = (
                SellerOrder.objects.select_related("order", "seller")
                .prefetch_related("items")
                .get(pk=seller_order_id)
            )
            order = seller_order.order
            item_lines = [
                f"- {item.product_name}: {item.quantity} {item.unit} x ₹{item.unit_price}"
                for item in seller_order.items.all()
            ]
            body = "\n".join(
                [
                    f"Hello {order.customer_name},",
                    f"Seller {seller_order.seller.company_name} updated its part of your order #{order.pk}.",
                    f"Seller order status: {seller_order.get_status_display()}",
                    f"Seller note: {seller_order.seller_notes or 'No additional note'}",
                    "Updated items:",
                    *item_lines,
                ]
            )
            _send(
                f"SupplyHub seller order update: #{order.pk}",
                body,
                [order.email],
            )
        except SellerOrder.DoesNotExist:
            logger.warning(
                "Seller order %s disappeared before its update notification was sent.",
                seller_order_id,
            )

    transaction.on_commit(send)


def notify_order_updated(order_id, changed_fields):
    changed = ", ".join(changed_fields)

    def send():
        try:
            order = Order.objects.get(pk=order_id)
            body = "\n".join(
                [
                    f"Hello {order.customer_name},",
                    f"Your SupplyHub order #{order.pk} has been updated.",
                    f"Status: {order.get_status_display()}",
                    f"Payment received: {'Yes' if order.payment_received else 'No'}",
                    f"Total: ₹{order.total_amount}",
                ]
            )
            _send(f"SupplyHub order update: #{order.pk}", body, [order.email])
            logger.info("Order #%s notification sent after changes: %s", order.pk, changed)
        except Order.DoesNotExist:
            logger.warning("Order %s disappeared before its update notification was sent.", order_id)

    transaction.on_commit(send)


def notify_order_cancelled(order_id):
    def send():
        try:
            order = Order.objects.prefetch_related(
                "seller_orders__seller"
            ).get(pk=order_id)
            seller_recipients = [
                seller_order.seller.email
                for seller_order in order.seller_orders.all()
            ]
            body = "\n".join(
                [
                    f"Order #{order.pk} was cancelled by the customer.",
                    f"Customer: {order.customer_name}",
                    f"Email: {order.email}",
                    f"Status: {order.get_status_display()}",
                ]
            )
            _send(
                f"SupplyHub order cancelled: #{order.pk}",
                body,
                seller_recipients + _admin_recipients(),
            )
        except Order.DoesNotExist:
            logger.warning(
                "Order %s disappeared before cancellation notifications were sent.",
                order_id,
            )

    transaction.on_commit(send)


def notify_quote_created(quote_id):
    def send():
        try:
            quote = QuoteRequest.objects.select_related(
                "seller",
                "product__seller",
            ).get(pk=quote_id)
            store = StoreSettings.load()
            seller = quote.seller or (quote.product.seller if quote.product_id else None)
            body = "\n".join(
                [
                    f"Quote request reference: {quote.reference}",
                    f"Customer: {quote.customer_name}",
                    f"Business: {quote.business_name or 'Not provided'}",
                    f"Product: {quote.product_name}",
                    f"Quantity: {quote.quantity}",
                    f"Seller: {seller.company_name}" if seller else "",
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
            if seller:
                _send(
                    f"New SupplyHub buyer inquiry: {quote.reference}",
                    body,
                    [seller.email],
                )
        except QuoteRequest.DoesNotExist:
            logger.warning("Quote request %s disappeared before its notification was sent.", quote_id)

    transaction.on_commit(send)


def notify_quote_updated(quote_id, changed_fields):
    changed = ", ".join(changed_fields)

    def send():
        try:
            quote = QuoteRequest.objects.select_related("seller").get(pk=quote_id)
            body = "\n".join(
                [
                    f"Hello {quote.customer_name},",
                    f"Your quote request {quote.reference} has been updated.",
                    f"Product: {quote.product_name}",
                    f"Quantity: {quote.quantity}",
                    f"Status: {quote.get_status_display()}",
                    (
                        f"Quoted unit price: ₹{quote.seller_quoted_unit_price}"
                        if quote.seller_quoted_unit_price is not None
                        else (
                            f"Quoted unit price: ₹{quote.quoted_unit_price}"
                            if quote.quoted_unit_price is not None
                            else ""
                        )
                    ),
                    f"Seller response: {quote.seller_response or quote.admin_response or 'No additional message'}",
                ]
            )
            _send(f"SupplyHub quote update: {quote.reference}", body, [quote.email])
            logger.info("Quote %s notification sent after changes: %s", quote.reference, changed)
        except QuoteRequest.DoesNotExist:
            logger.warning("Quote request %s disappeared before its update notification was sent.", quote_id)

    transaction.on_commit(send)

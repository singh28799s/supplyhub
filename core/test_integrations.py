import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Category,
    Order,
    OrderItem,
    PaymentTransaction,
    PaymentWebhookEvent,
    Product,
    SellerOrder,
    SellerPayout,
    SellerProfile,
)
from .payouts import PayoutNotReadyError, release_seller_payout
from .shipping import create_shipment, fetch_tracking
from .views import _mark_payment_captured


class RazorpayFlowTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            customer_name="Payment Buyer",
            email="pay@example.com",
            phone="9999999999",
            delivery_address="1 Pay Street",
            city="Jaipur",
            postal_code="302001",
            total_amount=Decimal("100.00"),
            payment_method=Order.PaymentMethod.RAZORPAY,
            payment_status=Order.PaymentStatus.PENDING,
        )
        self.payment = PaymentTransaction.objects.create(
            order=self.order,
            provider_order_id="order_test123",
            amount_paise=10000,
        )

    @override_settings(
        RAZORPAY_KEY_ID="rzp_test_key",
        RAZORPAY_KEY_SECRET="secret",
    )
    @patch("core.views.create_provider_order", return_value="order_checkout123")
    def test_online_checkout_reserves_stock_and_creates_provider_attempt(
        self,
        create_order_mock,
    ):
        category = Category.objects.create(name="Online checkout products")
        product = Product.objects.create(
            category=category,
            name="Online checkout item",
            price=Decimal("30.00"),
            minimum_order_quantity=1,
            track_inventory=True,
            stock_quantity=4,
        )
        session = self.client.session
        session["cart"] = {str(product.pk): 2}
        session.save()

        response = self.client.post(
            reverse("checkout"),
            {
                "customer_name": "Online Buyer",
                "email": "online@example.com",
                "phone": "9999999999",
                "delivery_address": "1 Online Road",
                "city": "Jaipur",
                "postal_code": "302001",
                "notes": "",
                "payment_method": Order.PaymentMethod.RAZORPAY,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/payment_checkout.html")
        create_order_mock.assert_called_once()
        transaction = PaymentTransaction.objects.get(order__email="online@example.com")
        order = transaction.order
        self.assertEqual(transaction.provider_order_id, "order_checkout123")
        self.assertEqual(transaction.amount_paise, 6000)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)
        self.assertTrue(order.items.get().stock_reserved)
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 2)

    @override_settings(
        RAZORPAY_KEY_ID="rzp_test_key",
        RAZORPAY_KEY_SECRET="secret",
    )
    @patch("core.views.fetch_payment")
    def test_checkout_signature_and_provider_capture_are_required(self, fetch_payment_mock):
        payment_id = "pay_test123"
        signature = hmac.new(
            b"secret",
            b"order_test123|pay_test123",
            hashlib.sha256,
        ).hexdigest()
        fetch_payment_mock.return_value = {
            "id": payment_id,
            "order_id": "order_test123",
            "amount": 10000,
            "status": "captured",
        }

        response = self.client.post(
            reverse("razorpay_verify"),
            data=json.dumps(
                {
                    "razorpay_order_id": "order_test123",
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertTrue(self.order.payment_received)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.CAPTURED)
        self.assertEqual(self.payment.provider_payment_id, payment_id)

    @override_settings(
        RAZORPAY_KEY_ID="rzp_test_key",
        RAZORPAY_KEY_SECRET="secret",
    )
    def test_invalid_checkout_signature_does_not_mark_order_paid(self):
        response = self.client.post(
            reverse("razorpay_verify"),
            data=json.dumps(
                {
                    "razorpay_order_id": "order_test123",
                    "razorpay_payment_id": "pay_fake",
                    "razorpay_signature": "invalid",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.order.refresh_from_db()
        self.assertFalse(self.order.payment_received)

    @override_settings(RAZORPAY_WEBHOOK_SECRET="webhook-secret")
    def test_captured_payment_webhook_is_signature_checked_and_idempotent(self):
        payload = json.dumps(
            {
                "event": "payment.captured",
                "payload": {
                    "payment": {
                        "entity": {
                            "id": "pay_webhook123",
                            "order_id": "order_test123",
                            "amount": 10000,
                            "status": "captured",
                        }
                    }
                },
            }
        ).encode()
        signature = hmac.new(b"webhook-secret", payload, hashlib.sha256).hexdigest()
        headers = {
            "HTTP_X_RAZORPAY_SIGNATURE": signature,
            "HTTP_X_RAZORPAY_EVENT_ID": "event_webhook123",
        }

        first = self.client.post(
            reverse("razorpay_webhook"),
            data=payload,
            content_type="application/json",
            **headers,
        )
        second = self.client.post(
            reverse("razorpay_webhook"),
            data=payload,
            content_type="application/json",
            **headers,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(PaymentWebhookEvent.objects.count(), 1)
        self.order.refresh_from_db()
        self.assertTrue(self.order.payment_received)

    def test_delivery_hold_and_five_percent_commission_gate_seller_payout(self):
        seller_user = get_user_model().objects.create_user(username="payoutseller")
        seller = SellerProfile.objects.create(
            user=seller_user,
            company_name="Payout seller",
            contact_name="Seller",
            email="seller@example.com",
            status=SellerProfile.Status.APPROVED,
            razorpay_linked_account_id="acc_test123",
        )
        category = Category.objects.create(name="Payout products")
        product = Product.objects.create(
            seller=seller,
            category=category,
            name="Payout item",
            price=Decimal("100.00"),
        )
        item = OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name=product.name,
            unit=product.unit,
            unit_price=Decimal("100.00"),
            quantity=1,
        )
        seller_order = SellerOrder.objects.create(
            order=self.order,
            seller=seller,
            status=SellerOrder.Status.COMPLETED,
            delivered_at=timezone.now(),
        )
        seller_order.items.add(item)
        self.payment.status = PaymentTransaction.Status.CAPTURED
        self.payment.provider_payment_id = "pay_test123"
        self.payment.save()
        payout = SellerPayout.objects.create(
            seller_order=seller_order,
            gross_amount=Decimal("100.00"),
            commission_rate=Decimal("5.00"),
            commission_amount=Decimal("5.00"),
            net_amount=Decimal("95.00"),
            status=SellerPayout.Status.HOLD,
            available_at=timezone.now() + timedelta(days=7),
        )

        with patch("core.payouts.create_seller_transfer") as transfer_mock:
            with self.assertRaises(PayoutNotReadyError):
                release_seller_payout(payout.pk)
            transfer_mock.assert_not_called()

            seller_order.delivered_at = timezone.now() - timedelta(days=8)
            seller_order.save(update_fields=["delivered_at"])
            payout.available_at = timezone.now() - timedelta(days=1)
            payout.save(update_fields=["available_at"])
            transfer_mock.return_value = {"id": "tr_test123"}
            transfer_id = release_seller_payout(payout.pk)

        self.assertEqual(transfer_id, "tr_test123")
        transfer_mock.assert_called_once_with(
            "pay_test123",
            linked_account_id="acc_test123",
            amount_paise=9500,
            reference=str(self.order.reference),
            seller_order_id=seller_order.pk,
        )
        payout.refresh_from_db()
        self.assertEqual(payout.status, SellerPayout.Status.PROCESSING)
        self.assertEqual(payout.razorpay_transfer_id, "tr_test123")

    def test_payment_capture_calculates_configured_commission(self):
        seller_user = get_user_model().objects.create_user(username="commission-seller")
        seller = SellerProfile.objects.create(
            user=seller_user,
            company_name="Commission seller",
            contact_name="Seller",
            email="commission@example.com",
            status=SellerProfile.Status.APPROVED,
        )
        category = Category.objects.create(name="Commission products")
        product = Product.objects.create(
            seller=seller,
            category=category,
            name="Commission item",
            price=Decimal("80.00"),
        )
        item = OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name=product.name,
            unit=product.unit,
            unit_price=Decimal("80.00"),
            quantity=1,
        )
        seller_order = SellerOrder.objects.create(order=self.order, seller=seller)
        seller_order.items.add(item)
        with override_settings(
            RAZORPAY_KEY_ID="rzp_test_key",
            RAZORPAY_KEY_SECRET="secret",
            SUPPLYHUB_SELLER_COMMISSION_PERCENT="5.00",
        ):
            _mark_payment_captured(self.payment, "pay_test123")

        payout = SellerPayout.objects.get(seller_order=seller_order)
        self.assertEqual(payout.gross_amount, Decimal("80.00"))
        self.assertEqual(payout.commission_amount, Decimal("4.00"))
        self.assertEqual(payout.net_amount, Decimal("76.00"))


@override_settings(
    DELHIVERY_API_TOKEN="test-token",
    DELHIVERY_PICKUP_LOCATION="Jaipur Warehouse",
    DELHIVERY_API_BASE_URL="https://staging-express.delhivery.com",
)
class DelhiveryApiTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            customer_name="Shipping Buyer",
            email="ship@example.com",
            phone="+91 9876543210",
            delivery_address="1 Ship Road",
            city="Jaipur",
            postal_code="302001",
            total_amount=Decimal("100.00"),
            payment_received=True,
        )
        seller_user = get_user_model().objects.create_user(username="shipseller")
        self.seller = SellerProfile.objects.create(
            user=seller_user,
            company_name="Shipping seller",
            contact_name="Seller",
            email="shipper@example.com",
        )
        category = Category.objects.create(name="Shipping products")
        product = Product.objects.create(
            seller=self.seller,
            category=category,
            name="Ship item",
            price=Decimal("100.00"),
        )
        item = OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name=product.name,
            unit=product.unit,
            unit_price=Decimal("100.00"),
            quantity=1,
        )
        self.seller_order = SellerOrder.objects.create(
            order=self.order,
            seller=self.seller,
        )
        self.seller_order.items.add(item)

    @patch("core.shipping.requests.request")
    def test_create_shipment_uses_token_auth_and_packed_dimensions(self, request_mock):
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "packages": [{"waybill": "1234567890", "refnum": "shipment-ref"}]
        }
        request_mock.return_value = response

        shipment = create_shipment(
            self.seller_order,
            {
                "package_weight_grams": 500,
                "package_length_cm": Decimal("20.00"),
                "package_width_cm": Decimal("10.00"),
                "package_height_cm": Decimal("8.00"),
            },
        )

        self.assertEqual(shipment["waybill"], "1234567890")
        self.assertEqual(
            request_mock.call_args.kwargs["headers"]["Authorization"],
            "Token test-token",
        )
        self.assertEqual(
            request_mock.call_args.kwargs["data"]["format"],
            "json",
        )

    @patch("core.shipping.requests.request")
    def test_tracking_status_and_scan_history_are_extracted(self, request_mock):
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "ShipmentData": [
                {
                    "Shipment": {
                        "Status": {
                            "Status": "Delivered",
                            "StatusDateTime": "2026-10-01T10:00:00+05:30",
                        },
                        "Scans": [
                            {
                                "ScanDetail": {
                                    "Scan": "Delivered",
                                    "Instructions": "Delivered to consignee",
                                    "ScanDateTime": "2026-10-01T10:00:00+05:30",
                                }
                            }
                        ],
                    }
                }
            ]
        }
        request_mock.return_value = response

        tracking = fetch_tracking("1234567890")

        self.assertEqual(tracking.status, "Delivered")
        self.assertEqual(tracking.scans[0]["status"], "Delivered")
        self.assertIsNotNone(tracking.status_time)

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .inventory import release_order_stock
from .models import Category, Order, OrderItem, Product


class InventoryReservationTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Tracked goods")
        self.product = Product.objects.create(
            category=category,
            name="Tracked wholesale item",
            price=Decimal("10.00"),
            minimum_order_quantity=2,
            track_inventory=True,
            stock_quantity=8,
        )

    def _checkout(self):
        response = self.client.post(
            reverse("checkout"),
            {
                "customer_name": "Stock Buyer",
                "email": "stockbuyer@example.com",
                "phone": "1234567890",
                "delivery_address": "1 Stock Street",
                "city": "Pune",
                "postal_code": "411001",
                "notes": "",
                "payment_method": Order.PaymentMethod.CASH_ON_DELIVERY,
            },
        )
        return response

    def test_checkout_reserves_stock_and_cancellation_releases_it_once(self):
        self.client.post(
            reverse("add_to_cart"),
            {"product_id": self.product.pk, "quantity": "5"},
        )

        response = self._checkout()

        order = Order.objects.get(email="stockbuyer@example.com")
        item = OrderItem.objects.get(order=order)
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 3)
        self.assertTrue(item.stock_reserved)

        release_order_stock(order.pk)
        release_order_stock(order.pk)

        self.product.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 8)
        self.assertFalse(item.stock_reserved)

    def test_checkout_rejects_quantity_above_available_stock(self):
        session = self.client.session
        session["cart"] = {str(self.product.pk): 9}
        session.save()

        response = self._checkout()

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Order.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 8)

    def test_untracked_product_does_not_reserve_stock(self):
        self.product.track_inventory = False
        self.product.stock_quantity = 0
        self.product.save()
        self.client.force_login(
            get_user_model().objects.create_user(username="untracked-buyer")
        )
        self.client.post(
            reverse("add_to_cart"),
            {"product_id": self.product.pk, "quantity": "2"},
        )

        self._checkout()

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)
        self.assertFalse(OrderItem.objects.get().stock_reserved)

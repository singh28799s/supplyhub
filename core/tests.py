from decimal import Decimal

from django.core import mail
from django.contrib.auth import get_user_model
from django.contrib.admin.sites import site
from django.test import TestCase
from django.test import override_settings
from django.test import RequestFactory
from django.urls import reverse

from .admin import OrderAdmin, QuoteRequestAdmin
from .models import Category, Order, OrderItem, Product
from .models import QuoteRequest, StoreSettings, Supplier


class HomePageTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Jute Bags")
        self.product = Product.objects.create(
            category=self.category,
            name="Reusable Jute Tote",
            price="25.00",
            minimum_order_quantity=100,
            is_featured=True,
        )

    def test_home_page_loads(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
        self.assertContains(response, self.category.name)
        self.assertContains(response, f'data-product-id="{self.product.pk}"')
        self.assertContains(response, 'data-category-name="Jute Bags"')
        self.assertContains(response, "getProductSearchScore")

    def test_home_page_uses_saved_store_branding(self):
        StoreSettings.objects.create(
            store_name="Northstar Supply",
            browser_title="Northstar | Wholesale",
            hero_eyebrow="SUPPLY FOR YOUR BUSINESS",
            hero_headline="Source better products.",
            brand_icon="bi-shop",
            primary_color="#123456",
        )

        response = self.client.get(reverse("home"))

        self.assertContains(response, "<title>Northstar | Wholesale</title>")
        self.assertContains(response, "Source better products.")
        self.assertContains(response, "SUPPLY FOR YOUR BUSINESS")
        self.assertContains(response, "Northstar Supply")
        self.assertContains(response, "--green: #123456;")
        self.assertContains(response, "bi-shop")

    def test_products_without_uploaded_image_get_svg_fallback(self):
        product = Product.objects.create(
            category=self.category,
            name="Bamboo Storage Basket",
            price="30.00",
            minimum_order_quantity=50,
            is_active=True,
        )

        self.assertTrue(product.display_image_url.startswith("data:image/svg+xml;base64,"))

    def test_inactive_products_are_not_shown(self):
        self.product.is_active = False
        self.product.save()

        response = self.client.get(reverse("home"))

        self.assertNotContains(response, self.product.name)

    def test_category_product_count_comes_from_database(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.context["categories"][0].product_count, 1)

    def test_product_detail_page_loads_with_description_and_images(self):
        self.product.description = "Heavy-duty reusable bag for retail and events."
        self.product.save()

        response = self.client.get(reverse("product_detail", args=[self.product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
        self.assertContains(response, "Heavy-duty reusable bag for retail and events.")
        self.assertContains(response, "Minimum order")
        self.assertContains(response, "Add to Cart")


class CustomerAuthenticationTests(TestCase):
    def test_registration_creates_customer_and_logs_them_in(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newbuyer",
                "email": "buyer@example.com",
                "password1": "SupplyHubBuyer!2026",
                "password2": "SupplyHubBuyer!2026",
            },
        )

        self.assertRedirects(response, reverse("home"))
        user = get_user_model().objects.get(username="newbuyer")
        self.assertEqual(user.email, "buyer@example.com")
        self.assertTrue(user.is_authenticated)
        self.assertFalse(user.is_staff)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_customer_can_log_in_and_log_out(self):
        user = get_user_model().objects.create_user(
            username="returningbuyer",
            password="SupplyHubBuyer!2026",
        )

        login_response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": "SupplyHubBuyer!2026"},
        )
        self.assertRedirects(login_response, reverse("home"))
        self.assertTrue(self.client.session.get("_auth_user_id"))

        logout_response = self.client.post(reverse("logout"))
        self.assertRedirects(logout_response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_registration_rejects_mismatched_passwords(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "buyer",
                "email": "buyer@example.com",
                "password1": "SupplyHubBuyer!2026",
                "password2": "DifferentPassword!2026",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="buyer").exists())


class CustomerOrderTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Bulk Bags")
        self.product = Product.objects.create(
            category=self.category,
            name="Wholesale Jute Bag",
            price="12.50",
            sample_price="25.00",
            sample_quantity=1,
            unit="piece",
            minimum_order_quantity=10,
        )

    def add_product_to_cart(self):
        return self.client.post(
            reverse("add_to_cart"),
            {"product_id": self.product.pk},
        )

    def test_customer_can_cancel_pending_order_and_reserved_stock_is_released(self):
        customer = get_user_model().objects.create_user(
            username="cancelbuyer",
            email="cancelbuyer@example.com",
            password="CancelBuyerPass!2026",
        )
        tracked_product = Product.objects.create(
            category=self.category,
            name="Reserved Jute Bags",
            price="12.50",
            track_inventory=True,
            stock_quantity=3,
        )
        order = Order.objects.create(
            customer=customer,
            customer_name="Cancel Buyer",
            email=customer.email,
            phone="1234567890",
            delivery_address="1 Test Street",
            city="Jaipur",
            postal_code="302001",
            total_amount="25.00",
        )
        item = OrderItem.objects.create(
            order=order,
            product=tracked_product,
            product_name=tracked_product.name,
            unit=tracked_product.unit,
            unit_price=tracked_product.price,
            quantity=2,
            stock_reserved=True,
        )
        self.client.force_login(customer)

        orders_page = self.client.get(reverse("my_orders"))
        self.assertContains(orders_page, "Cancel order")

        response = self.client.post(
            reverse("cancel_order", args=[order.pk]),
        )

        self.assertRedirects(response, reverse("my_orders"))
        order.refresh_from_db()
        item.refresh_from_db()
        tracked_product.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertFalse(item.stock_reserved)
        self.assertEqual(tracked_product.stock_quantity, 5)
        self.assertNotContains(self.client.get(reverse("my_orders")), "Cancel order")

    def test_customer_cannot_cancel_another_customers_order(self):
        owner = get_user_model().objects.create_user(
            username="orderowner",
            password="OrderOwnerPass!2026",
        )
        other_customer = get_user_model().objects.create_user(
            username="notowner",
            password="NotOwnerPass!2026",
        )
        order = Order.objects.create(
            customer=owner,
            customer_name="Order Owner",
            email="owner@example.com",
            phone="1234567890",
            delivery_address="1 Test Street",
            city="Jaipur",
            postal_code="302001",
        )
        self.client.force_login(other_customer)

        response = self.client.post(reverse("cancel_order", args=[order.pk]))

        self.assertEqual(response.status_code, 404)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_paid_order_requires_support_for_cancellation_and_refund(self):
        customer = get_user_model().objects.create_user(
            username="paidbuyer",
            password="PaidBuyerPass!2026",
        )
        order = Order.objects.create(
            customer=customer,
            customer_name="Paid Buyer",
            email="paid@example.com",
            phone="1234567890",
            delivery_address="1 Test Street",
            city="Jaipur",
            postal_code="302001",
            payment_method=Order.PaymentMethod.RAZORPAY,
            payment_status=Order.PaymentStatus.CAPTURED,
            payment_received=True,
        )
        self.client.force_login(customer)

        orders_page = self.client.get(reverse("my_orders"))
        self.assertNotContains(orders_page, "Cancel order")
        self.assertContains(orders_page, "Paid orders need refund review.")

        self.client.post(reverse("cancel_order", args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_add_to_cart_uses_product_moq(self):
        response = self.add_product_to_cart()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cart_count"], 10)
        cart_response = self.client.get(reverse("cart"))
        self.assertContains(cart_response, "value=\"10\"")

    def test_sample_order_uses_sample_price(self):
        home_response = self.client.get(reverse("home"))
        self.assertContains(home_response, "Sample: 1 piece")
        self.assertContains(home_response, "₹25.00")
        self.assertContains(home_response, "Order sample")

        response = self.client.post(reverse("buy_sample", args=[self.product.pk]))

        self.assertRedirects(response, reverse("checkout"))
        checkout_response = self.client.get(reverse("checkout"))
        self.assertContains(checkout_response, "1 × ₹25.00")
        self.assertContains(checkout_response, "₹25.00")

        placed_response = self.client.post(
            reverse("checkout"),
            {
                "customer_name": "Sample Buyer",
                "email": "sample@example.com",
                "phone": "+911234567890",
                "delivery_address": "1 Sample Street",
                "city": "Jaipur",
                "postal_code": "302001",
                "notes": "Sample first",
                "payment_method": Order.PaymentMethod.CASH_ON_DELIVERY,
            },
        )

        order = Order.objects.get(customer_name="Sample Buyer")
        item = order.items.get()
        self.assertRedirects(
            placed_response,
            reverse("order_confirmation", kwargs={"reference": order.reference}),
        )
        self.assertEqual(item.unit_price, Decimal("25.00"))
        self.assertEqual(order.total_amount, Decimal("25.00"))
        self.assertTrue(item.is_sample)

    def test_wholesale_quantity_uses_wholesale_price(self):
        self.client.post(
            reverse("add_to_cart"),
            {"product_id": self.product.pk},
        )
        self.client.post(
            reverse("update_cart", args=[self.product.pk]),
            {"action": "update", "quantity": "25"},
        )

        cart_response = self.client.get(reverse("cart"))

        self.assertContains(cart_response, "₹12.50 / piece")
        self.assertContains(cart_response, "₹312.50")

    def test_offer_price_is_used_for_wholesale_cart_and_order(self):
        self.product.offer_price = Decimal("10.00")
        self.product.save()
        self.add_product_to_cart()

        cart_response = self.client.get(reverse("cart"))
        self.assertContains(cart_response, "₹10.00 / piece")
        self.assertContains(cart_response, "₹100.00")

        self.client.post(
            reverse("checkout"),
            {
                "customer_name": "Offer Buyer",
                "email": "offer@example.com",
                "phone": "+911234567890",
                "delivery_address": "1 Offer Street",
                "city": "Jaipur",
                "postal_code": "302001",
                "notes": "",
                "payment_method": Order.PaymentMethod.CASH_ON_DELIVERY,
            },
        )
        order = Order.objects.get(customer_name="Offer Buyer")
        self.assertEqual(order.total_amount, Decimal("100.00"))
        self.assertEqual(order.items.get().unit_price, Decimal("10.00"))

    def test_checkout_applies_shipping_and_persists_selected_bank_transfer(self):
        store_settings = StoreSettings.load()
        store_settings.shipping_charge = Decimal("50.00")
        store_settings.free_shipping_threshold = Decimal("5000.00")
        store_settings.cash_on_delivery_enabled = False
        store_settings.bank_transfer_enabled = True
        store_settings.bank_transfer_instructions = "Transfer to account details supplied by seller."
        store_settings.save()
        self.add_product_to_cart()

        checkout_response = self.client.get(reverse("checkout"))
        self.assertContains(checkout_response, "₹175.00")
        self.assertContains(checkout_response, "Bank transfer")

        response = self.client.post(
            reverse("checkout"),
            {
                "customer_name": "Transfer Buyer",
                "email": "transfer@example.com",
                "phone": "+911234567890",
                "delivery_address": "1 Transfer Street",
                "city": "Jaipur",
                "postal_code": "302001",
                "notes": "",
                "payment_method": Order.PaymentMethod.BANK_TRANSFER,
            },
        )

        order = Order.objects.get(customer_name="Transfer Buyer")
        self.assertRedirects(
            response,
            reverse("order_confirmation", kwargs={"reference": order.reference}),
        )
        self.assertEqual(order.shipping_charge, Decimal("50.00"))
        self.assertEqual(order.total_amount, Decimal("175.00"))
        self.assertEqual(order.payment_method, Order.PaymentMethod.BANK_TRANSFER)
        self.assertFalse(order.payment_received)
        self.assertContains(self.client.get(response.url), "Transfer to account details")

    def test_in_between_sample_and_moq_quantity_is_rejected(self):
        self.add_product_to_cart()

        response = self.client.post(
            reverse("update_cart", args=[self.product.pk]),
            {"action": "update", "quantity": "5"},
        )

        self.assertRedirects(response, reverse("cart"))
        self.assertContains(self.client.get(reverse("cart")), "value=\"10\"")

    def test_buy_now_adds_minimum_quantity_and_opens_checkout(self):
        other_product = Product.objects.create(
            category=self.category,
            name="Other Jute Bag",
            price="5.00",
            minimum_order_quantity=2,
        )
        self.client.post(reverse("add_to_cart"), {"product_id": other_product.pk})

        response = self.client.post(reverse("buy_now", args=[self.product.pk]))

        self.assertRedirects(response, reverse("checkout"))
        self.assertContains(self.client.get(reverse("checkout")), self.product.name)
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 10})

    def test_sample_buy_is_unavailable_without_sample_price(self):
        self.product.sample_price = None
        self.product.save()

        response = self.client.post(reverse("buy_sample", args=[self.product.pk]))

        self.assertRedirects(response, reverse("home"))
        self.assertNotIn(str(self.product.pk), self.client.session.get("cart", {}))

    def test_wishlist_toggle_persists_and_renders_active_heart(self):
        response = self.client.post(
            reverse("toggle_wishlist"),
            {"product_id": self.product.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["added"])
        self.assertIn(str(self.product.pk), self.client.session["wishlist"])
        self.assertContains(self.client.get(reverse("home")), "aria-pressed=\"true\"")

        remove_response = self.client.post(
            reverse("toggle_wishlist"),
            {"product_id": self.product.pk},
        )
        self.assertFalse(remove_response.json()["added"])
        self.assertEqual(self.client.session["wishlist"], [])

    def test_wishlist_page_displays_saved_products(self):
        self.client.post(
            reverse("toggle_wishlist"),
            {"product_id": self.product.pk},
        )

        response = self.client.get(reverse("wishlist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)

    def test_cart_quantity_cannot_be_lower_than_moq(self):
        self.add_product_to_cart()

        response = self.client.post(
            reverse("update_cart", args=[self.product.pk]),
            {"action": "update", "quantity": "5"},
        )

        self.assertRedirects(response, reverse("cart"))
        self.assertContains(self.client.get(reverse("cart")), "value=\"10\"")

    def test_guest_checkout_persists_order_and_clears_cart(self):
        self.add_product_to_cart()
        response = self.client.post(
            reverse("checkout"),
            {
                "customer_name": "Test Buyer",
                "email": "buyer@example.com",
                "phone": "+911234567890",
                "delivery_address": "10 Market Road",
                "city": "Jaipur",
                "postal_code": "302001",
                "notes": "Please call before delivery",
                "payment_method": Order.PaymentMethod.CASH_ON_DELIVERY,
            },
        )

        order = Order.objects.get(customer_name="Test Buyer")
        item = OrderItem.objects.get(order=order)
        self.assertRedirects(
            response,
            reverse("order_confirmation", kwargs={"reference": order.reference}),
        )
        self.assertEqual(order.total_amount, Decimal("125.00"))
        self.assertEqual(item.product_name, self.product.name)
        self.assertEqual(item.quantity, 10)
        self.assertEqual(self.client.session["cart"], {})
        self.assertContains(self.client.get(response.url), f"Order ID:</strong> #{order.pk}")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        SUPPLYHUB_ADMIN_EMAIL="orders@example.com",
    )
    def test_order_confirmation_and_staff_notification_are_emailed(self):
        self.add_product_to_cart()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("checkout"),
                {
                    "customer_name": "Email Buyer",
                    "email": "emailbuyer@example.com",
                    "phone": "+911234567890",
                    "delivery_address": "2 Mail Road",
                    "city": "Jaipur",
                    "postal_code": "302001",
                    "notes": "",
                    "payment_method": Order.PaymentMethod.CASH_ON_DELIVERY,
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ["emailbuyer@example.com"])
        self.assertEqual(mail.outbox[1].to, ["orders@example.com"])
        order = Order.objects.get(email="emailbuyer@example.com")
        self.assertIn(f"Order ID: #{order.pk}", mail.outbox[0].body)
        self.assertIn(f"Order ID: #{order.pk}", mail.outbox[1].body)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_order_status_change_emails_customer(self):
        order = Order.objects.create(
            customer_name="Status Buyer",
            email="statusbuyer@example.com",
            phone="1234567890",
            delivery_address="3 Status Street",
            city="Jaipur",
            postal_code="302001",
        )
        order.status = Order.Status.CONFIRMED

        with self.captureOnCommitCallbacks(execute=True):
            OrderAdmin(Order, site).save_model(
                RequestFactory().post("/admin/core/order/1/change/"),
                order,
                form=None,
                change=True,
            )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["statusbuyer@example.com"])
        self.assertIn("confirmed", mail.outbox[0].body.lower())
        self.assertIn(f"order #{order.pk}", mail.outbox[0].body.lower())

    def test_checkout_rejects_invalid_email_and_does_not_create_order(self):
        self.add_product_to_cart()

        response = self.client.post(
            reverse("checkout"),
            {
                "customer_name": "Test Buyer",
                "email": "not-an-email",
                "phone": "+911234567890",
                "delivery_address": "10 Market Road",
                "city": "Jaipur",
                "postal_code": "302001",
                "notes": "",
                "payment_method": Order.PaymentMethod.CASH_ON_DELIVERY,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())

    def test_signed_in_customer_can_see_only_their_orders(self):
        user = get_user_model().objects.create_user(
            username="buyer",
            password="SupplyHubBuyer!2026",
        )
        self.client.force_login(user)
        self.add_product_to_cart()
        self.client.post(
            reverse("checkout"),
            {
                "customer_name": "Test Buyer",
                "email": "buyer@example.com",
                "phone": "+911234567890",
                "delivery_address": "10 Market Road",
                "city": "Jaipur",
                "postal_code": "302001",
                "notes": "",
                "payment_method": Order.PaymentMethod.CASH_ON_DELIVERY,
            },
        )

        order = Order.objects.get(customer=user)
        response = self.client.get(reverse("my_orders"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Order #{order.pk}")


class QuoteRequestTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Quote Bags")
        self.product = Product.objects.create(
            category=category,
            name="Custom Printed Jute Tote",
            price="20.00",
            minimum_order_quantity=100,
        )

    def test_guest_can_submit_product_quote_request(self):
        response = self.client.post(
            reverse("quote_request"),
            {
                "customer_name": "Quote Buyer",
                "business_name": "Buyer Co",
                "email": "quote@example.com",
                "phone": "+911234567890",
                "product": self.product.pk,
                "quantity": 500,
                "message": "Print our logo on both sides.",
            },
        )

        quote = QuoteRequest.objects.get()
        self.assertRedirects(
            response,
            reverse("quote_confirmation", kwargs={"reference": quote.reference}),
        )
        self.assertEqual(quote.product, self.product)
        self.assertEqual(quote.product_name, self.product.name)
        self.assertEqual(quote.quantity, 500)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        SUPPLYHUB_ADMIN_EMAIL="quotes@example.com",
    )
    def test_quote_submission_emails_buyer_and_staff(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("quote_request"),
                {
                    "customer_name": "Email Quote Buyer",
                    "business_name": "Quote Co",
                    "email": "quote-buyer@example.com",
                    "phone": "+911234567890",
                    "product": self.product.pk,
                    "quantity": 300,
                    "message": "Need custom branding.",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ["quote-buyer@example.com"])
        self.assertEqual(mail.outbox[1].to, ["quotes@example.com"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_quote_response_emails_customer(self):
        quote = QuoteRequest.objects.create(
            customer_name="Response Buyer",
            email="responsebuyer@example.com",
            phone="1234567890",
            product=self.product,
            product_name=self.product.name,
            quantity=200,
        )
        quote.status = QuoteRequest.Status.QUOTED
        quote.quoted_unit_price = Decimal("17.50")
        quote.admin_response = "Valid for 30 days."

        with self.captureOnCommitCallbacks(execute=True):
            QuoteRequestAdmin(QuoteRequest, site).save_model(
                RequestFactory().post("/admin/core/quoterequest/1/change/"),
                quote,
                form=None,
                change=True,
            )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["responsebuyer@example.com"])
        self.assertIn("17.50", mail.outbox[0].body)

    def test_quote_rejects_zero_quantity(self):
        response = self.client.post(
            reverse("quote_request"),
            {
                "customer_name": "Quote Buyer",
                "business_name": "",
                "email": "quote@example.com",
                "phone": "+911234567890",
                "product": self.product.pk,
                "quantity": 0,
                "message": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(QuoteRequest.objects.exists())

    def test_signed_in_customer_can_view_their_quote_requests(self):
        customer = get_user_model().objects.create_user(
            username="quotebuyer",
            password="QuoteBuyerPassword!2026",
        )
        self.client.force_login(customer)
        self.client.post(
            reverse("quote_request"),
            {
                "customer_name": "Quote Buyer",
                "business_name": "Buyer Co",
                "email": "quote@example.com",
                "phone": "+911234567890",
                "product": self.product.pk,
                "quantity": 500,
                "message": "Need a custom logo.",
            },
        )

        quote = QuoteRequest.objects.get()
        response = self.client.get(reverse("my_quotes"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(quote.reference))


class StoreSettingsTests(TestCase):
    def test_shipping_and_free_shipping_threshold(self):
        settings = StoreSettings.objects.create(
            shipping_charge="100.00",
            free_shipping_threshold="5000.00",
        )

        self.assertEqual(settings.shipping_for_subtotal(Decimal("4999.99")), Decimal("100.00"))
        self.assertEqual(settings.shipping_for_subtotal(Decimal("5000.00")), Decimal("0.00"))

    def test_supplier_records_can_be_saved(self):
        supplier = Supplier.objects.create(
            company_name="Jute Maker Ltd",
            contact_name="Supplier Contact",
            email="supplier@example.com",
        )

        self.assertEqual(Supplier.objects.get(pk=supplier.pk).company_name, "Jute Maker Ltd")

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Category, Order, OrderItem, Product, QuoteRequest, StoreSettings, Supplier


class DashboardAccessTests(TestCase):
    def test_anonymous_user_is_redirected_to_admin_login(self):
        response = self.client.get(reverse("dashboard:index"))

        self.assertRedirects(
            response,
            f"{reverse('admin:login')}?next={reverse('dashboard:index')}",
        )

    def test_regular_customer_cannot_open_dashboard(self):
        customer = get_user_model().objects.create_user(
            username="customer",
            password="CustomerPassword!2026",
        )
        self.client.force_login(customer)

        response = self.client.get(reverse("dashboard:index"))

        self.assertRedirects(
            response,
            f"{reverse('admin:login')}?next={reverse('dashboard:index')}",
        )

    def test_staff_dashboard_shows_catalog_and_order_summary(self):
        staff = get_user_model().objects.create_superuser(
            username="staff",
            email="staff@example.com",
            password="StaffPassword!2026",
        )
        category = Category.objects.create(name="Test Category")
        product = Product.objects.create(
            category=category,
            name="Test Wholesale Product",
            price="15.00",
            minimum_order_quantity=5,
        )
        order = Order.objects.create(
            customer_name="Buyer Name",
            email="buyer@example.com",
            phone="1234567890",
            delivery_address="1 Test Street",
            city="Jaipur",
            postal_code="302001",
            total_amount="75.00",
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            unit=product.unit,
            unit_price=product.price,
            quantity=5,
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["category_count"], 1)
        self.assertEqual(response.context["product_count"], 1)
        self.assertEqual(response.context["order_count"], 1)
        self.assertEqual(response.context["customer_count"], 0)
        self.assertEqual(response.context["total_sales"], 75)
        self.assertContains(response, str(order.reference)[:8])
        self.assertContains(response, "Test Wholesale Product")
        self.assertContains(response, "Test Category")
        self.assertContains(response, reverse("admin:core_order_changelist"))
        self.assertContains(response, reverse("admin:core_product_add"))
        self.assertContains(response, 'method="post"')

    def test_staff_dashboard_logout_uses_post_and_logs_user_out(self):
        staff = get_user_model().objects.create_superuser(
            username="logoutadmin",
            email="logout@example.com",
            password="LogoutAdminPassword!2026",
        )
        self.client.force_login(staff)

        response = self.client.post(reverse("admin:logout"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_staff_can_save_shipping_settings(self):
        staff = get_user_model().objects.create_superuser(
            username="settingsadmin",
            email="settings@example.com",
            password="SettingsAdminPassword!2026",
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("dashboard:index"),
            {
                "form_type": "shipping",
                "shipping-shipping_charge": "50.00",
                "shipping-free_shipping_threshold": "5000.00",
                "shipping-cash_on_delivery_enabled": "on",
                "shipping-bank_transfer_enabled": "on",
                "shipping-bank_transfer_instructions": "Use supplied invoice reference.",
            },
        )

        self.assertRedirects(response, reverse("dashboard:index"))
        settings = StoreSettings.objects.get(pk=1)
        self.assertEqual(settings.shipping_charge, Decimal("50.00"))
        self.assertEqual(settings.free_shipping_threshold, Decimal("5000.00"))

    def test_staff_can_change_store_notification_email(self):
        staff = get_user_model().objects.create_superuser(
            username="emailsettingsadmin",
            email="admin-settings@example.com",
            password="EmailSettingsPassword!2026",
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("dashboard:index"),
            {
                "form_type": "store",
                "store-store_name": "SupplyHub",
                "store-tagline": "Wholesale store",
                "store-support_phone": "1234567890",
                "store-support_email": "singh28799@gmail.com",
                "store-address": "Jaipur",
                "store-delivery_note": "Delivery across India",
            },
        )

        self.assertRedirects(response, reverse("dashboard:index"))
        self.assertEqual(StoreSettings.objects.get(pk=1).support_email, "singh28799@gmail.com")

    def test_dashboard_lists_database_quotes_suppliers_and_offers(self):
        staff = get_user_model().objects.create_superuser(
            username="commerceadmin",
            email="commerce@example.com",
            password="CommerceAdminPassword!2026",
        )
        category = Category.objects.create(name="Commerce Category")
        supplier = Supplier.objects.create(company_name="Commerce Supplier")
        product = Product.objects.create(
            category=category,
            supplier=supplier,
            name="Commerce Product",
            price="20.00",
            offer_price="18.00",
        )
        quote = QuoteRequest.objects.create(
            customer_name="Quote Customer",
            business_name="Quote Company",
            email="quote@example.com",
            phone="1234567890",
            product=product,
            product_name=product.name,
            quantity=250,
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.context["quote_count"], 1)
        self.assertEqual(response.context["supplier_count"], 1)
        self.assertContains(response, str(quote.reference)[:8])
        self.assertContains(response, "Commerce Supplier")
        self.assertContains(response, "Commerce Product")
        self.assertContains(response, reverse("admin:core_quoterequest_change", args=[quote.pk]))

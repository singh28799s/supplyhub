from datetime import timedelta
from decimal import Decimal
import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.signing import TimestampSigner
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .seller_security import EMAIL_VERIFICATION_SALT, normalize_seller_phone
from .models import (
    Category,
    Order,
    Product,
    ProductAttribute,
    ProductPriceTier,
    QuoteRequest,
    SellerLoginChallenge,
    SellerOrder,
    SellerProfile,
)


class SellerMarketplaceTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Electronics")
        self.seller_user = get_user_model().objects.create_user(
            username="sellerone",
            email="one@example.com",
            password="SellerPassword123!",
        )
        self.seller = SellerProfile.objects.create(
            user=self.seller_user,
            company_name="One Electronics",
            contact_name="Seller One",
            email="one@example.com",
            phone="9876543210",
            email_verified=True,
            status=SellerProfile.Status.APPROVED,
        )
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name="Wholesale Display",
            description="A full display description.",
            price="1200.00",
            minimum_order_quantity=10,
            visible_detail_fields=[
                "description",
                "price",
                "moq",
                "attributes",
                "seller",
            ],
        )

    def test_seller_signup_creates_pending_profile_and_login(self):
        response = self.client.post(
            reverse("seller_register"),
            {
                "username": "newmanufacturer",
                "email": "maker@example.com",
                "company_name": "Maker Company",
                "contact_name": "Maker Contact",
                "phone": "+919876543210",
                "country": "India",
                "city": "Pune",
                "business_type": SellerProfile.BusinessType.MANUFACTURER,
                "years_in_business": "3",
                "description": "Wholesale manufacturer profile.",
                "password1": "DifferentSellerPass!823",
                "password2": "DifferentSellerPass!823",
            },
        )

        self.assertRedirects(response, reverse("seller_mfa"))
        profile = SellerProfile.objects.get(company_name="Maker Company")
        self.assertEqual(profile.status, SellerProfile.Status.PENDING)
        self.assertEqual(profile.user.username, "newmanufacturer")
        self.assertTrue(self.client.session.get("_auth_user_id"))
        self.assertFalse(profile.email_verified)
        self.assertEqual(profile.phone, "+919876543210")
        self.assertEqual(profile.products.count(), 0)

    def login_as_seller(self, user, profile=None):
        profile = profile or user.seller_profile
        self.client.force_login(user)
        session = self.client.session
        session["seller_mfa_verified_user_id"] = user.pk
        session["seller_mfa_verified_phone"] = normalize_seller_phone(
            profile.phone,
            profile.country,
        )
        session.save()

    def test_seller_dashboard_route_redirects_anonymous_users_to_login(self):
        self.assertEqual(reverse("seller_dashboard"), "/seller/dashboard/")

        response = self.client.get(reverse("seller_dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('seller_dashboard')}",
        )

    def test_seller_dashboard_route_opens_for_authenticated_seller(self):
        response = self.client.get(reverse("seller_dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

        self.login_as_seller(self.seller_user)
        response = self.client.get(reverse("seller_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Seller dashboard")

    def test_seller_login_requires_email_and_sms_verification(self):
        self.seller_user.set_password("SecureSellerPassword!823")
        self.seller_user.save(update_fields=["password"])

        response = self.client.post(
            reverse("login"),
            {
                "username": self.seller_user.username,
                "password": "SecureSellerPassword!823",
            },
        )

        self.assertRedirects(response, reverse("seller_mfa"))
        self.assertNotIn("seller_mfa_verified_user_id", self.client.session)
        with patch("core.views.send_seller_sms_verification") as send_sms:
            response = self.client.post(
                reverse("seller_mfa"),
                {"action": "send_code"},
            )
        self.assertEqual(response.status_code, 200)
        send_sms.assert_called_once_with("+919876543210")
        challenge = self.seller_user.seller_login_challenges.latest("created_at")

        with patch("core.views.check_seller_sms_verification", return_value=True) as check_sms:
            response = self.client.post(
                reverse("seller_mfa"),
                {"action": "verify", "code": "123456"},
            )

        check_sms.assert_called_once_with("+919876543210", "123456")
        self.assertRedirects(response, reverse("seller_dashboard"))
        self.assertTrue(
            self.seller_user.seller_login_challenges.get(pk=challenge.pk).consumed
        )
        self.assertEqual(
            self.client.session["seller_mfa_verified_user_id"],
            self.seller_user.pk,
        )

    def test_seller_routes_are_blocked_until_mfa_is_verified(self):
        self.client.force_login(self.seller_user)

        response = self.client.get(reverse("seller_products"))

        self.assertRedirects(response, reverse("seller_mfa"))

    def test_sms_verification_send_is_rate_limited(self):
        self.client.force_login(self.seller_user)
        with patch("core.views.send_seller_sms_verification") as send_sms:
            first = self.client.post(
                reverse("seller_mfa"),
                {"action": "send_code"},
            )
            second = self.client.post(
                reverse("seller_mfa"),
                {"action": "send_code"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        send_sms.assert_called_once_with("+919876543210")
        self.assertEqual(
            SellerLoginChallenge.objects.filter(user=self.seller_user).count(),
            1,
        )

    def test_sms_verification_allows_only_five_code_checks(self):
        self.client.force_login(self.seller_user)
        challenge = SellerLoginChallenge.objects.create(
            user=self.seller_user,
            phone="+919876543210",
        )
        with patch("core.views.check_seller_sms_verification", return_value=False) as check_sms:
            for _ in range(5):
                self.client.post(
                    reverse("seller_mfa"),
                    {"action": "verify", "code": "123456"},
                )
            self.client.post(
                reverse("seller_mfa"),
                {"action": "verify", "code": "123456"},
            )

        challenge.refresh_from_db()
        self.assertEqual(challenge.attempts, 5)
        self.assertEqual(check_sms.call_count, 5)

    def test_unverified_seller_email_cannot_request_sms_code(self):
        self.seller.email_verified = False
        self.seller.save(update_fields=["email_verified"])
        self.client.force_login(self.seller_user)

        with patch("core.views.send_seller_sms_verification") as send_sms:
            response = self.client.post(
                reverse("seller_mfa"),
                {"action": "send_code"},
            )

        self.assertEqual(response.status_code, 200)
        send_sms.assert_not_called()
        self.assertFalse(SellerLoginChallenge.objects.filter(user=self.seller_user).exists())

    def test_seller_email_link_requires_post_confirmation(self):
        profile = self.seller
        profile.email_verified = False
        profile.save(update_fields=["email_verified"])
        token = TimestampSigner(salt=EMAIL_VERIFICATION_SALT).sign(
            f"{profile.pk}:{profile.email.casefold()}"
        )
        url = reverse("seller_email_verify", kwargs={"token": token})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertFalse(profile.email_verified)

        response = self.client.post(url)

        self.assertRedirects(response, reverse("login"))
        profile.refresh_from_db()
        self.assertTrue(profile.email_verified)

    def test_email_resend_sends_otp_and_only_stores_a_hash(self):
        self.seller.email_verified = False
        self.seller.save(update_fields=["email_verified"])
        self.client.force_login(self.seller_user)

        with patch("core.seller_security.send_mail", return_value=1) as send_mail:
            response = self.client.post(
                reverse("seller_mfa"),
                {"action": "email_resend"},
            )

        self.assertEqual(response.status_code, 200)
        send_mail.assert_called_once()
        body = send_mail.call_args.args[1]
        match = re.search(r"(?m)^(\d{6})$", body)
        self.assertIsNotNone(match)
        self.seller.refresh_from_db()
        self.assertTrue(
            check_password(
                match.group(1),
                self.seller.email_verification_code_hash,
            ),
        )
        self.assertNotEqual(
            self.seller.email_verification_code_hash,
            match.group(1),
        )
        self.assertEqual(self.seller.email_verification_code_attempts, 0)
        self.assertGreater(
            self.seller.email_verification_code_expires_at,
            timezone.now(),
        )

    def test_email_resend_obeys_cooldown_and_hourly_limit(self):
        self.seller.email_verified = False
        self.seller.save(update_fields=["email_verified"])
        self.client.force_login(self.seller_user)

        with patch("core.seller_security.send_mail", return_value=1) as send_mail:
            self.client.post(reverse("seller_mfa"), {"action": "email_resend"})
            cooldown_response = self.client.post(
                reverse("seller_mfa"),
                {"action": "email_resend"},
            )
            self.assertContains(
                cooldown_response,
                "Please wait one minute before requesting another verification email.",
            )

            self.seller.refresh_from_db()
            self.seller.email_verification_sent_at = (
                timezone.now() - timedelta(minutes=2)
            )
            self.seller.email_verification_window_started_at = timezone.now()
            self.seller.email_verification_send_count = 5
            self.seller.save(
                update_fields=[
                    "email_verification_sent_at",
                    "email_verification_window_started_at",
                    "email_verification_send_count",
                ]
            )
            hourly_limit_response = self.client.post(
                reverse("seller_mfa"),
                {"action": "email_resend"},
            )
            self.assertContains(
                hourly_limit_response,
                "Too many verification emails were requested",
            )

        send_mail.assert_called_once()

    def test_correct_email_otp_verifies_once_and_clears_code(self):
        self.seller.email_verified = False
        self.seller.email_verification_code_hash = make_password("123456")
        self.seller.email_verification_code_expires_at = (
            timezone.now() + timedelta(minutes=10)
        )
        self.seller.save(
            update_fields=[
                "email_verified",
                "email_verification_code_hash",
                "email_verification_code_expires_at",
            ]
        )
        self.client.force_login(self.seller_user)

        response = self.client.post(
            reverse("seller_mfa"),
            {"action": "email_verify", "code": "123456"},
        )

        self.assertEqual(response.status_code, 200)
        self.seller.refresh_from_db()
        self.assertTrue(self.seller.email_verified)
        self.assertEqual(self.seller.email_verification_code_hash, "")
        self.assertIsNone(self.seller.email_verification_code_expires_at)

    def test_email_otp_expires_and_wrong_attempts_are_limited(self):
        self.seller.email_verified = False
        self.seller.email_verification_code_hash = make_password("123456")
        self.seller.email_verification_code_expires_at = (
            timezone.now() - timedelta(seconds=1)
        )
        self.seller.save(
            update_fields=[
                "email_verified",
                "email_verification_code_hash",
                "email_verification_code_expires_at",
            ]
        )
        self.client.force_login(self.seller_user)
        expired = self.client.post(
            reverse("seller_mfa"),
            {"action": "email_verify", "code": "123456"},
        )
        self.assertContains(expired, "Your email code expired")
        self.seller.refresh_from_db()
        self.assertFalse(self.seller.email_verified)

        self.seller.email_verification_code_expires_at = (
            timezone.now() + timedelta(minutes=10)
        )
        self.seller.email_verification_code_attempts = 4
        self.seller.save(
            update_fields=[
                "email_verification_code_expires_at",
                "email_verification_code_attempts",
            ]
        )
        wrong = self.client.post(
            reverse("seller_mfa"),
            {"action": "email_verify", "code": "654321"},
        )
        self.assertContains(wrong, "That email code is not valid")
        self.seller.refresh_from_db()
        self.assertEqual(self.seller.email_verification_code_attempts, 5)
        locked = self.client.post(
            reverse("seller_mfa"),
            {"action": "email_verify", "code": "654321"},
        )
        self.assertContains(locked, "Too many code attempts")
        self.seller.refresh_from_db()
        self.assertEqual(self.seller.email_verification_code_attempts, 5)

    @override_settings(
        DEBUG=False,
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    )
    def test_production_console_email_backend_reports_configuration_error(self):
        self.seller.email_verified = False
        self.seller.save(update_fields=["email_verified"])
        self.client.force_login(self.seller_user)

        response = self.client.post(
            reverse("seller_mfa"),
            {"action": "email_resend"},
        )

        self.assertContains(response, "Production email is set to console mode")
        self.seller.refresh_from_db()
        self.assertFalse(self.seller.email_verification_code_hash)

    def test_password_reset_route_is_available(self):
        response = self.client.get(reverse("password_reset"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="email"')

    def test_logged_in_buyer_can_apply_to_become_a_seller(self):
        buyer_user = get_user_model().objects.create_user(
            username="buyerapplicant",
            email="buyer@example.com",
            password="BuyerPassword123!",
        )
        self.client.force_login(buyer_user)

        response = self.client.post(
            reverse("seller_register"),
            {
                "company_name": "Buyer Turns Manufacturer",
                "contact_name": "Seller One",
                "email": "buyer@example.com",
                "phone": "+919876543210",
                "country": "India",
                "city": "Delhi",
                "business_type": SellerProfile.BusinessType.TRADING_COMPANY,
                "years_in_business": "2",
                "description": "A new seller application.",
                "customization_capabilities": "",
                "certifications": "",
            },
        )

        self.assertRedirects(response, reverse("seller_mfa"))
        self.assertEqual(
            SellerProfile.objects.get(user=buyer_user).status,
            SellerProfile.Status.PENDING,
        )
        self.assertFalse(SellerProfile.objects.get(user=buyer_user).email_verified)

    def test_unapproved_seller_product_is_not_published(self):
        pending_user = get_user_model().objects.create_user(
            username="waiting",
            password="SellerPassword123!",
        )
        pending = SellerProfile.objects.create(
            user=pending_user,
            company_name="Waiting Manufacturer",
            contact_name="Awaiting Review",
            email="waiting@example.com",
        )
        hidden = Product.objects.create(
            seller=pending,
            category=self.category,
            name="Pending Display",
            price="100.00",
            is_active=True,
        )

        home = self.client.get(reverse("home"))
        product_detail = self.client.get(
            reverse("product_detail", args=[hidden.slug])
        )
        public_shop = self.client.get(
            reverse("seller_public_profile", args=[pending.slug])
        )

        self.assertNotContains(home, hidden.name)
        self.assertEqual(product_detail.status_code, 404)
        self.assertEqual(public_shop.status_code, 404)

    def test_unapproved_seller_can_only_save_a_private_product_draft(self):
        pending_user = get_user_model().objects.create_user(
            username="waitingmaker",
            password="SellerPassword123!",
        )
        pending = SellerProfile.objects.create(
            user=pending_user,
            company_name="Waiting Company",
            contact_name="Awaiting Approval",
            email="waiting@example.com",
            phone="9876543210",
            email_verified=True,
        )
        self.login_as_seller(pending_user, pending)

        response = self.client.post(
            reverse("seller_product_create"),
            {
                "category": self.category.pk,
                "name": "Private Draft Product",
                "price": "50.00",
                "sample_quantity": "1",
                "unit": "piece",
                "minimum_order_quantity": "5",
                "stock_quantity": "0",
                "visible_detail_fields": ["price", "moq"],
                "attributes_text": "",
                "price_tiers_text": "",
                "customizations_text": "",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("seller_products"))
        draft = Product.objects.get(name="Private Draft Product")
        self.assertEqual(draft.seller, pending)
        self.assertFalse(draft.is_active)
        self.assertNotContains(self.client.get(reverse("home")), draft.name)

    def test_product_form_checkbox_groups_use_layout_safe_widget_class(self):
        self.login_as_seller(self.seller_user)

        response = self.client.get(reverse("seller_product_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'id="id_visible_detail_fields" class="seller-checkbox-widget"',
        )
        self.assertNotContains(
            response,
            'id="id_visible_detail_fields" class="form-check-input"',
        )

    def test_seller_can_manage_price_tiers_attributes_and_visibility(self):
        self.login_as_seller(self.seller_user)
        response = self.client.post(
            reverse("seller_product_create"),
            {
                "category": self.category.pk,
                "name": "Custom Desk Display",
                "description": "Made to order for business buyers.",
                "price": "15.00",
                "minimum_order_quantity": "10",
                "sample_quantity": "1",
                "unit": "piece",
                "badge": "Customizable",
                "stock_quantity": "0",
                "visible_detail_fields": ["description", "price", "moq", "price_tiers", "attributes", "customizations", "seller"],
                "attributes_text": "Screen size: 55 inches\nBrand: Example",
                "price_tiers_text": "10-99: 15.00\n100+: 12.50",
                "customizations_text": "Custom logo | 2.00 | 20",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("seller_products"))
        product = Product.objects.get(name="Custom Desk Display")
        self.assertEqual(product.seller, self.seller)
        self.assertTrue(product.is_active)
        self.assertEqual(product.unit_price_for_quantity(99), Decimal("15.00"))
        self.assertEqual(product.unit_price_for_quantity(100), Decimal("12.50"))
        self.assertEqual(product.attributes.count(), 2)
        self.assertEqual(product.customizations.count(), 1)
        self.assertIn("customizations", product.visible_detail_fields)

    def test_seller_can_hide_selected_public_product_details(self):
        ProductAttribute.objects.create(
            product=self.product,
            name="Factory location",
            value="Internal only",
        )
        self.login_as_seller(self.seller_user)
        response = self.client.post(
            reverse("seller_product_edit", args=[self.product.pk]),
            {
                "category": self.category.pk,
                "name": self.product.name,
                "description": self.product.description,
                "price": "1200.00",
                "sample_quantity": "1",
                "minimum_order_quantity": "10",
                "unit": "piece",
                "stock_quantity": "0",
                "visible_detail_fields": ["moq", "attributes"],
                "attributes_text": "Material: Steel\nFactory location: Internal only",
                "hidden_attributes": ["Factory location"],
                "price_tiers_text": "",
                "customizations_text": "",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("seller_products"))
        detail = self.client.get(reverse("product_detail", args=[self.product.slug]))
        self.assertNotContains(detail, "A full display description.")
        self.assertNotContains(detail, "₹1,200.00")
        self.assertNotContains(detail, "Add to Cart")
        self.assertNotContains(detail, "Internal only")
        self.assertContains(detail, "Material")
        add_response = self.client.post(
            reverse("add_to_cart"),
            {"product_id": self.product.pk, "quantity": "10"},
        )
        self.assertEqual(add_response.status_code, 400)
        self.assertFalse(self.client.session.get("cart"))
        self.assertContains(detail, "MOQ 10 piece")
        self.assertEqual(
            Product.objects.get(pk=self.product.pk).visible_detail_fields,
            ["moq", "attributes"],
        )

    def test_product_edit_and_orders_are_scoped_to_the_signed_in_seller(self):
        other_user = get_user_model().objects.create_user(
            username="sellertwo",
            password="SellerPassword123!",
        )
        other_seller = SellerProfile.objects.create(
            user=other_user,
            company_name="Other Electronics",
            contact_name="Seller Two",
            email="two@example.com",
            email_verified=True,
            status=SellerProfile.Status.APPROVED,
        )
        other_product = Product.objects.create(
            seller=other_seller,
            category=self.category,
            name="Other Display",
            price="80.00",
            minimum_order_quantity=2,
        )
        order = Order.objects.create(
            customer_name="Buyer",
            email="buyer@example.com",
            phone="123",
            delivery_address="1 Example Road",
            city="Pune",
            postal_code="411001",
        )
        seller_order = SellerOrder.objects.create(order=order, seller=other_seller)

        self.login_as_seller(self.seller_user)
        product_response = self.client.get(
            reverse("seller_product_edit", args=[other_product.pk])
        )
        order_response = self.client.post(
            reverse("seller_order_update", args=[seller_order.pk]),
            {"status": SellerOrder.Status.CONFIRMED, "seller_notes": "Not mine"},
        )

        self.assertEqual(product_response.status_code, 404)
        self.assertEqual(order_response.status_code, 404)
        self.assertEqual(seller_order.status, SellerOrder.Status.PENDING)

    def test_checkout_creates_isolated_seller_orders_and_vendor_status_does_not_change_marketplace_order(self):
        ProductPriceTier.objects.create(
            product=self.product,
            minimum_quantity=10,
            unit_price="1100.00",
        )
        other_user = get_user_model().objects.create_user(
            username="sellertwo",
            password="SellerPassword123!",
        )
        other_seller = SellerProfile.objects.create(
            user=other_user,
            company_name="Other Wholesale Co",
            contact_name="Seller Two",
            email="two@example.com",
            email_verified=True,
            status=SellerProfile.Status.APPROVED,
        )
        other_product = Product.objects.create(
            seller=other_seller,
            category=self.category,
            name="Wholesale Keyboard",
            price="25.00",
            minimum_order_quantity=2,
        )
        customer = get_user_model().objects.create_user(
            username="buyer",
            password="BuyerPassword123!",
        )
        self.client.force_login(customer)
        session = self.client.session
        session["cart"] = {
            str(self.product.pk): 10,
            str(other_product.pk): 2,
        }
        session.save()

        response = self.client.post(
            reverse("checkout"),
            {
                "customer_name": "Buyer",
                "email": "buyer@example.com",
                "phone": "1234567890",
                "delivery_address": "1 Example Road",
                "city": "Pune",
                "postal_code": "411001",
                "notes": "",
                "payment_method": Order.PaymentMethod.CASH_ON_DELIVERY,
            },
        )

        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(email="buyer@example.com")
        seller_order = SellerOrder.objects.get(order=order, seller=self.seller)
        other_seller_order = SellerOrder.objects.get(order=order, seller=other_seller)
        self.assertEqual(list(seller_order.items.values_list("product_id", flat=True)), [self.product.pk])
        self.assertEqual(
            seller_order.items.get(product=self.product).unit_price,
            Decimal("1100.00"),
        )
        self.assertEqual(
            list(other_seller_order.items.values_list("product_id", flat=True)),
            [other_product.pk],
        )

        self.login_as_seller(self.seller_user)
        update_response = self.client.post(
            reverse("seller_order_update", args=[seller_order.pk]),
            {"status": SellerOrder.Status.CONFIRMED, "seller_notes": "Order confirmed"},
        )

        self.assertRedirects(update_response, reverse("seller_orders"))
        seller_order.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(seller_order.status, SellerOrder.Status.CONFIRMED)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(seller_order.seller_notes, "Order confirmed")
        self.assertEqual(other_seller_order.status, SellerOrder.Status.PENDING)

    def test_seller_can_reply_to_only_their_own_quote(self):
        quote = QuoteRequest.objects.create(
            product=self.product,
            product_name=self.product.name,
            quantity=50,
            customer_name="Buyer",
            email="buyer@example.com",
            phone="9876543210",
        )
        self.login_as_seller(self.seller_user)

        response = self.client.post(
            reverse("seller_quotes"),
            {
                "quote_id": quote.pk,
                "seller_quoted_unit_price": "1000.00",
                "seller_response": "Price includes bulk packaging.",
            },
        )

        self.assertRedirects(response, reverse("seller_quotes"))
        quote.refresh_from_db()
        self.assertEqual(quote.seller_quoted_unit_price, Decimal("1000.00"))
        self.assertEqual(quote.seller_response, "Price includes bulk packaging.")
        self.assertEqual(quote.seller, self.seller)
        self.assertEqual(quote.status, QuoteRequest.Status.QUOTED)
        self.assertIsNotNone(quote.seller_responded_at)

    def test_buyer_can_send_a_quote_directly_to_a_seller_store(self):
        profile_page = self.client.get(
            reverse("seller_public_profile", args=[self.seller.slug])
        )
        self.assertContains(profile_page, f"?seller={self.seller.slug}")

        response = self.client.post(
            f"{reverse('quote_request')}?seller={self.seller.slug}",
            {
                "customer_name": "Buyer",
                "business_name": "Buyer Company",
                "email": "buyer@example.com",
                "phone": "1234567890",
                "product": "",
                "seller": self.seller.pk,
                "quantity": "100",
                "message": "Please share your wholesale catalog.",
            },
        )

        self.assertEqual(response.status_code, 302)
        quote = QuoteRequest.objects.get(email="buyer@example.com")
        self.assertEqual(quote.seller, self.seller)
        self.assertIsNone(quote.product)
        self.login_as_seller(self.seller_user)
        seller_quotes = self.client.get(reverse("seller_quotes"))
        self.assertContains(seller_quotes, "Please share your wholesale catalog.")

    def test_seller_cannot_submit_overlapping_quantity_price_tiers(self):
        self.login_as_seller(self.seller_user)
        response = self.client.post(
            reverse("seller_product_create"),
            {
                "category": self.category.pk,
                "name": "Broken tier display",
                "description": "",
                "price": "20.00",
                "minimum_order_quantity": "10",
                "sample_quantity": "1",
                "unit": "piece",
                "visible_detail_fields": ["price", "moq"],
                "attributes_text": "",
                "price_tiers_text": "10-100: 20.00\n80+: 15.00",
                "customizations_text": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("price_tiers_text", response.context["form"].errors)
        self.assertFalse(Product.objects.filter(name="Broken tier display").exists())

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Category, Product, PromotionCampaign


class MarketplaceHomeTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Office Supplies")
        self.product = Product.objects.create(
            category=self.category,
            name="Recycled Paper Notebook",
            price="120.00",
            offer_price="99.00",
            minimum_order_quantity=50,
            is_featured=True,
        )

    def test_homepage_shows_marketplace_sections_and_wholesale_catalog(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wholesale sourcing")
        self.assertContains(response, "Shop by category")
        self.assertContains(response, "New arrivals")
        self.assertContains(response, "Offers for your next order")
        self.assertContains(response, "Wholesale product catalog")
        self.assertContains(response, self.product.name)
        self.assertContains(response, "MOQ: 50")
        self.assertContains(response, reverse("product_detail", args=[self.product.slug]))
        self.assertContains(response, 'id="searchInput"')
        self.assertContains(response, 'id="productGrid"')
        self.assertContains(response, "/static/core/css/home.css")

    def test_homepage_only_shows_campaigns_within_active_schedule(self):
        live_campaign = PromotionCampaign.objects.create(
            name="Season launch",
            eyebrow="BUSINESS BUYER OFFER",
            headline="A current campaign",
            description="A published wholesale promotion.",
            button_target=PromotionCampaign.ButtonTarget.PRODUCT,
            product=self.product,
        )
        PromotionCampaign.objects.create(
            name="Future launch",
            headline="Not live yet",
            starts_at=timezone.now() + timedelta(days=1),
        )
        PromotionCampaign.objects.create(
            name="Paused launch",
            headline="Paused campaign",
            is_active=False,
        )

        response = self.client.get(reverse("home"))

        self.assertEqual(list(response.context["campaigns"]), [live_campaign])
        self.assertContains(response, "A current campaign")
        self.assertContains(response, reverse("product_detail", args=[self.product.slug]))
        self.assertNotContains(response, "Not live yet")
        self.assertNotContains(response, "Paused campaign")
        self.assertNotContains(response, "Wholesale sourcing,<br><span>made simple.")

    def test_campaign_with_product_target_requires_a_product(self):
        campaign = PromotionCampaign(
            name="Product campaign",
            headline="Featured item",
            button_target=PromotionCampaign.ButtonTarget.PRODUCT,
        )

        with self.assertRaises(ValidationError):
            campaign.full_clean()

    def test_campaign_end_time_must_follow_start_time(self):
        now = timezone.now()
        campaign = PromotionCampaign(
            name="Invalid schedule",
            headline="Invalid promotion",
            starts_at=now,
            ends_at=now - timedelta(minutes=1),
        )

        with self.assertRaises(ValidationError):
            campaign.full_clean()


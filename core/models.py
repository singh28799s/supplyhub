import base64
import uuid
from decimal import Decimal
from html import escape

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, blank=True)
    description = models.TextField(blank=True)
    
    image=models.ImageField(upload_to="categories/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "category"
            self.slug = base_slug
            suffix = 2
            while Category.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{suffix}"
                suffix += 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Supplier(models.Model):
    company_name = models.CharField(max_length=180, unique=True)
    contact_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    gstin = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["company_name"]

    def __str__(self):
        return self.company_name


class SellerProfile(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class BusinessType(models.TextChoices):
        MANUFACTURER = "manufacturer", "Manufacturer"
        TRADING_COMPANY = "trading", "Trading company"
        DISTRIBUTOR = "distributor", "Distributor"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_profile",
    )
    company_name = models.CharField(max_length=180, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    contact_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    country = models.CharField(max_length=100, default="India")
    city = models.CharField(max_length=100, blank=True)
    business_type = models.CharField(
        max_length=20,
        choices=BusinessType.choices,
        default=BusinessType.MANUFACTURER,
    )
    years_in_business = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)
    customization_capabilities = models.TextField(blank=True)
    certifications = models.TextField(blank=True)
    logo = models.ImageField(upload_to="sellers/logos/", blank=True, null=True)
    cover_image = models.ImageField(upload_to="sellers/covers/", blank=True, null=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    review_notes = models.TextField(blank=True)
    razorpay_linked_account_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_name"]
        verbose_name = "seller profile"
        verbose_name_plural = "seller profiles"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.company_name) or "seller"
            self.slug = base_slug
            suffix = 2
            while SellerProfile.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{suffix}"
                suffix += 1
        super().save(*args, **kwargs)

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED and self.user.is_active

    def __str__(self):
        return self.company_name


PRODUCT_DETAIL_FIELDS = (
    ("description", "Full product description"),
    ("price", "Wholesale price"),
    ("moq", "Minimum order quantity"),
    ("offer", "Offer price"),
    ("sample", "Sample option"),
    ("price_tiers", "Quantity-based price tiers"),
    ("customizations", "Customization options"),
    ("badge", "Product badge"),
    ("attributes", "Product specifications"),
    ("seller", "Seller profile details"),
    ("stock", "Stock availability"),
)


def default_product_detail_fields():
    return [choice[0] for choice in PRODUCT_DETAIL_FIELDS]


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        related_name="products",
        null=True,
        blank=True,
    )
    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.SET_NULL,
        related_name="products",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    offer_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Optional promotional unit price; must be below the wholesale price.",
    )
    sample_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional price for exactly the sample quantity.",
    )
    sample_quantity = models.PositiveIntegerField(default=1)
    unit = models.CharField(max_length=30, default="piece")
    minimum_order_quantity = models.PositiveIntegerField(default=1)
    track_inventory = models.BooleanField(default=False)
    stock_quantity = models.PositiveIntegerField(default=0)
    shipping_weight_grams = models.PositiveIntegerField(null=True, blank=True)
    shipping_length_cm = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    shipping_width_cm = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    shipping_height_cm = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    badge = models.CharField(max_length=40, blank=True)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    
    image_url = models.URLField(blank=True)
    visible_detail_fields = models.JSONField(default=default_product_detail_fields)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_featured", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "product"
            self.slug = base_slug
            suffix = 2
            while Product.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{suffix}"
                suffix += 1
        super().save(*args, **kwargs)

    @property
    def display_image_url(self):
        if self.image and getattr(self.image, "url", None):
            return self.image.url
        if self.image_url:
            return self.image_url
        if self.category_id and self.category and self.category.image and getattr(self.category.image, "url", None):
            return self.category.image.url

        product_name = (self.name or "Product")[:28]
        category_name = self.category.name if self.category_id and self.category else "Wholesale"
        svg = f"""
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 900">
          <defs>
            <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
              <stop offset="0%" stop-color="#d9f7d9"/>
              <stop offset="100%" stop-color="#d9ebff"/>
            </linearGradient>
          </defs>
          <rect width="900" height="900" fill="url(#g)" rx="36"/>
          <circle cx="450" cy="250" r="150" fill="#ffffff" fill-opacity="0.2"/>
          <rect x="270" y="420" width="360" height="180" rx="26" fill="#ffffff" fill-opacity="0.18"/>
          <text x="50%" y="60%" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="54" fill="#165a36" font-weight="700">{escape(product_name)}</text>
          <text x="50%" y="71%" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="30" fill="#234e77" letter-spacing="2">{escape(category_name.upper())}</text>
        </svg>
        """.strip()
        return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")

    def __str__(self):
        return self.name

    def unit_price_for_quantity(self, quantity):
        if self.sample_price is not None and quantity == self.sample_quantity:
            return self.sample_price
        for tier in self.price_tiers.all():
            if tier.minimum_quantity <= quantity and (
                tier.maximum_quantity is None or tier.maximum_quantity >= quantity
            ):
                return tier.unit_price
        if self.offer_price is not None and self.offer_price < self.price:
            return self.offer_price
        return self.price

    @property
    def wholesale_price(self):
        first_tier = next(iter(self.price_tiers.all()), None)
        if first_tier:
            return first_tier.unit_price
        if self.offer_price is not None and self.offer_price < self.price:
            return self.offer_price
        return self.price

    @property
    def is_directly_orderable(self):
        return "price" in self.visible_detail_fields

    @property
    def has_orderable_inventory(self):
        return (
            not self.track_inventory
            or self.stock_quantity >= self.minimum_order_quantity
        )

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        shipping_values = (
            self.shipping_weight_grams,
            self.shipping_length_cm,
            self.shipping_width_cm,
            self.shipping_height_cm,
        )
        if any(value is not None for value in shipping_values) and not all(
            value is not None for value in shipping_values
        ):
            errors["__all__"] = (
                "Enter the shipping weight and all three dimensions together."
            )
        if self.offer_price is not None and self.offer_price >= self.price:
            errors["offer_price"] = "Offer price must be lower than the wholesale price."
        if self.sample_price is not None and self.sample_quantity >= self.minimum_order_quantity:
            errors["sample_quantity"] = "Sample quantity must be lower than the wholesale minimum order quantity."
        if errors:
            raise ValidationError(errors)


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="gallery_images",
    )
    image = models.ImageField(upload_to="products/gallery/")
    alt_text = models.CharField(max_length=180, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.alt_text or f"Image for {self.product.name}"


class ProductAttribute(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="attributes",
    )
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=250)
    is_visible = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "name"],
                name="unique_product_attribute_name",
            ),
        ]

    def __str__(self):
        return f"{self.name}: {self.value}"


class ProductPriceTier(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="price_tiers",
    )
    minimum_quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    maximum_quantity = models.PositiveIntegerField(null=True, blank=True)
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        ordering = ["minimum_quantity"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "minimum_quantity"],
                name="unique_product_price_tier_start",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(maximum_quantity__isnull=True)
                    | models.Q(maximum_quantity__gte=models.F("minimum_quantity"))
                ),
                name="product_price_tier_valid_range",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.maximum_quantity is not None and self.maximum_quantity < self.minimum_quantity:
            raise ValidationError({"maximum_quantity": "The end quantity must not be below the start."})
        overlapping = ProductPriceTier.objects.filter(product=self.product).exclude(pk=self.pk)
        for other in overlapping:
            if (
                (self.maximum_quantity is None or other.minimum_quantity <= self.maximum_quantity)
                and (other.maximum_quantity is None or self.minimum_quantity <= other.maximum_quantity)
            ):
                raise ValidationError("Price tier ranges for a product must not overlap.")

    def __str__(self):
        upper = self.maximum_quantity if self.maximum_quantity is not None else "up"
        return f"{self.minimum_quantity}-{upper}: {self.unit_price}"


class ProductCustomization(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="customizations",
    )
    name = models.CharField(max_length=120)
    additional_unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    minimum_quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "name"],
                name="unique_product_customization_name",
            ),
        ]

    def __str__(self):
        return self.name


class PromotionCampaign(models.Model):
    class ButtonTarget(models.TextChoices):
        PRODUCTS = "products", "Product catalogue"
        CATEGORIES = "categories", "Shop categories"
        QUOTE = "quote", "Request a bulk quote"
        PRODUCT = "product", "A specific product"

    name = models.CharField(max_length=120, help_text="Internal name shown in admin.")
    eyebrow = models.CharField(max_length=80, blank=True)
    headline = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="campaigns/", blank=True, null=True)
    button_label = models.CharField(max_length=40, default="Explore products")
    button_target = models.CharField(
        max_length=20,
        choices=ButtonTarget.choices,
        default=ButtonTarget.PRODUCTS,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        related_name="promotion_campaigns",
        null=True,
        blank=True,
        help_text="Required when the button targets a specific product.",
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "-id"]
        verbose_name = "promotion campaign"
        verbose_name_plural = "promotion campaigns"

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "The end time must be later than the start time."
        if self.button_target == self.ButtonTarget.PRODUCT and not self.product_id:
            errors["product"] = "Choose a product for this campaign button."
        if self.button_target != self.ButtonTarget.PRODUCT and self.product_id:
            errors["product"] = "Choose the product button target to link a specific product."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name

    @classmethod
    def active_now(cls):
        from django.utils import timezone

        now = timezone.now()
        return cls.objects.filter(is_active=True).filter(
            models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now),
            models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now),
        )


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending confirmation"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentMethod(models.TextChoices):
        CASH_ON_DELIVERY = "cash_on_delivery", "Cash on delivery"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        RAZORPAY = "razorpay", "Online payment (Razorpay)"

    class PaymentStatus(models.TextChoices):
        NOT_REQUIRED = "not_required", "Not required"
        OFFLINE_PENDING = "offline_pending", "Awaiting offline payment"
        PENDING = "pending", "Payment pending"
        CAPTURED = "captured", "Paid"
        FAILED = "failed", "Payment failed"
        REFUNDED = "refunded", "Refunded"

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="supplyhub_orders",
        null=True,
        blank=True,
    )
    customer_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    delivery_address = models.TextField()
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH_ON_DELIVERY,
    )
    payment_received = models.BooleanField(default=False)
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.OFFLINE_PENDING,
    )
    shipping_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} ({self.customer_name})"


class QuoteRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        QUOTED = "quoted", "Quote sent"
        ACCEPTED = "accepted", "Accepted"
        CLOSED = "closed", "Closed"

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="supplyhub_quotes",
        null=True,
        blank=True,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        related_name="quote_requests",
        null=True,
        blank=True,
    )
    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.SET_NULL,
        related_name="quote_requests",
        null=True,
        blank=True,
    )
    product_name = models.CharField(max_length=180, blank=True)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    customer_name = models.CharField(max_length=150)
    business_name = models.CharField(max_length=180, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    message = models.TextField(blank=True)
    quoted_unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    seller_quoted_unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    seller_response = models.TextField(blank=True)
    seller_responded_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    admin_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Quote {self.reference} ({self.customer_name})"


class StoreSettings(models.Model):
    store_name = models.CharField(max_length=120, default="SupplyHub")
    browser_title = models.CharField(
        max_length=160,
        default="SupplyHub | Business Wholesale Marketplace",
    )
    tagline = models.CharField(max_length=200, blank=True)
    hero_eyebrow = models.CharField(max_length=80, default="YOUR BUSINESS SOURCING PARTNER")
    hero_headline = models.CharField(max_length=180, default="Wholesale sourcing, made simple.")
    brand_icon = models.CharField(
        max_length=40,
        default="bi-box-seam",
        choices=[
            ("bi-box-seam", "Box"),
            ("bi-bag", "Bag"),
            ("bi-shop", "Shop"),
            ("bi-buildings", "Buildings"),
            ("bi-leaf", "Leaf"),
            ("bi-stars", "Stars"),
        ],
    )
    logo = models.ImageField(upload_to="branding/", blank=True)
    favicon = models.ImageField(upload_to="branding/", blank=True)
    primary_color = models.CharField(
        max_length=7,
        default="#0F766E",
        validators=[
            RegexValidator(
                r"^#[0-9A-Fa-f]{6}$",
                "Enter a valid hex color, such as #0F766E.",
            )
        ],
    )
    primary_dark_color = models.CharField(
        max_length=7,
        default="#134E4A",
        validators=[
            RegexValidator(
                r"^#[0-9A-Fa-f]{6}$",
                "Enter a valid hex color, such as #134E4A.",
            )
        ],
    )
    accent_color = models.CharField(
        max_length=7,
        default="#B99A62",
        validators=[
            RegexValidator(
                r"^#[0-9A-Fa-f]{6}$",
                "Enter a valid hex color, such as #B99A62.",
            )
        ],
    )
    page_background_color = models.CharField(
        max_length=7,
        default="#F6F5F2",
        validators=[
            RegexValidator(
                r"^#[0-9A-Fa-f]{6}$",
                "Enter a valid hex color, such as #F6F5F2.",
            )
        ],
    )
    text_color = models.CharField(
        max_length=7,
        default="#172025",
        validators=[
            RegexValidator(
                r"^#[0-9A-Fa-f]{6}$",
                "Enter a valid hex color, such as #172025.",
            )
        ],
    )
    support_phone = models.CharField(max_length=30, blank=True)
    support_email = models.EmailField(blank=True)
    address = models.CharField(max_length=250, blank=True)
    delivery_note = models.CharField(max_length=250, blank=True)
    shipping_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    free_shipping_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    cash_on_delivery_enabled = models.BooleanField(default=True)
    bank_transfer_enabled = models.BooleanField(default=False)
    bank_transfer_instructions = models.TextField(blank=True)

    class Meta:
        verbose_name = "store settings"
        verbose_name_plural = "store settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        settings_obj, _ = cls.objects.get_or_create(pk=1)
        return settings_obj

    def __str__(self):
        return f"Settings for {self.store_name}"

    def shipping_for_subtotal(self, subtotal):
        threshold = (
            Decimal(str(self.free_shipping_threshold))
            if self.free_shipping_threshold is not None
            else None
        )
        if threshold is not None and subtotal >= threshold:
            return Decimal("0.00")
        return Decimal(str(self.shipping_charge))


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        related_name="order_items",
        null=True,
        blank=True,
    )
    product_name = models.CharField(max_length=180)
    unit = models.CharField(max_length=30)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    is_sample = models.BooleanField(default=False)
    stock_reserved = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"


class SellerOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting seller confirmation"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        COMPLETED = "completed", "Completed"

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="seller_orders",
    )
    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    items = models.ManyToManyField(OrderItem, related_name="seller_orders")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    seller_notes = models.TextField(blank=True)
    delhivery_shipment_id = models.CharField(max_length=100, blank=True)
    delhivery_waybill = models.CharField(max_length=100, blank=True)
    delhivery_status = models.CharField(max_length=100, blank=True)
    package_weight_grams = models.PositiveIntegerField(null=True, blank=True)
    package_length_cm = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    package_width_cm = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    package_height_cm = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "seller"],
                name="unique_seller_order",
            ),
        ]

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.all()), Decimal("0.00"))

    def __str__(self):
        return f"Order #{self.order_id} — {self.seller.company_name}"


class PaymentTransaction(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        CAPTURED = "captured", "Captured"
        FAILED = "failed", "Failed"

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="payment_transaction",
    )
    provider_order_id = models.CharField(max_length=100, unique=True)
    provider_payment_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    amount_paise = models.PositiveBigIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CREATED)
    failure_reason = models.CharField(max_length=250, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class PaymentWebhookEvent(models.Model):
    provider_event_id = models.CharField(max_length=150, unique=True)
    event_type = models.CharField(max_length=100)
    received_at = models.DateTimeField(auto_now_add=True)


class SellerPayout(models.Model):
    class Status(models.TextChoices):
        WAITING_DELIVERY = "waiting_delivery", "Waiting for delivery"
        HOLD = "hold", "Seven-day hold"
        READY = "ready", "Ready for staff release"
        PROCESSING = "processing", "Transfer submitted"
        PAID = "paid", "Transferred"
        FAILED = "failed", "Transfer failed"

    seller_order = models.OneToOneField(
        SellerOrder,
        on_delete=models.PROTECT,
        related_name="payout",
    )
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("5.00"))
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING_DELIVERY,
    )
    available_at = models.DateTimeField(null=True, blank=True)
    razorpay_transfer_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class ShippingEvent(models.Model):
    seller_order = models.ForeignKey(
        SellerOrder,
        on_delete=models.CASCADE,
        related_name="shipping_events",
    )
    status = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    occurred_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-created_at"]

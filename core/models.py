import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=12, default="📦")
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
    badge = models.CharField(max_length=40, blank=True)
    icon = models.CharField(max_length=12, default="📦")
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    image_url = models.URLField(blank=True)
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

    def __str__(self):
        return self.name

    def unit_price_for_quantity(self, quantity):
        if self.sample_price is not None and quantity == self.sample_quantity:
            return self.sample_price
        if self.offer_price is not None and self.offer_price < self.price:
            return self.offer_price
        return self.price

    @property
    def wholesale_price(self):
        if self.offer_price is not None and self.offer_price < self.price:
            return self.offer_price
        return self.price

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.offer_price is not None and self.offer_price >= self.price:
            errors["offer_price"] = "Offer price must be lower than the wholesale price."
        if self.sample_price is not None and self.sample_quantity >= self.minimum_order_quantity:
            errors["sample_quantity"] = "Sample quantity must be lower than the wholesale minimum order quantity."
        if errors:
            raise ValidationError(errors)


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
    shipping_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order {self.reference} ({self.customer_name})"


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
    tagline = models.CharField(max_length=200, blank=True)
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

    class Meta:
        ordering = ["id"]

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"

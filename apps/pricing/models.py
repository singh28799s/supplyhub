from django.conf import settings
from django.db import models

from apps.catalog.models import Product


class PriceList(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ProductPrice(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="prices")
    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name="product_prices")
    retail_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    wholesale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    dealer_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    distributor_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    min_order_quantity = models.PositiveIntegerField(default=1)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("product", "price_list")

    def __str__(self):
        return f"{self.product.name} @ {self.price_list.name}"


class QuantityPrice(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="quantity_prices")
    min_quantity = models.PositiveIntegerField(default=1)
    max_quantity = models.PositiveIntegerField(null=True, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["min_quantity"]

    def __str__(self):
        return f"{self.product.name} - {self.min_quantity}+ @ ₹{self.unit_price}"


class CustomerSpecificPrice(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_prices")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="customer_prices")
    price = models.DecimalField(max_digits=12, decimal_places=2)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "product")

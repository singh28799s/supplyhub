from django.db import models


class Brand(models.Model):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to="brands/", blank=True, null=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    parent = models.ForeignKey("self", null=True, blank=True, related_name="children", on_delete=models.SET_NULL)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Attribute(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class AttributeValue(models.Model):
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE, related_name="values")
    value = models.CharField(max_length=120)

    class Meta:
        unique_together = ("attribute", "value")

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class Product(models.Model):
    PRODUCT_TYPES = [
        ("simple", "Simple"),
        ("variable", "Variable"),
        ("bundle", "Bundle"),
    ]

    sku = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    short_description = models.CharField(max_length=250, blank=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES, default="simple")
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("published", "Published"), ("archived", "Archived")], default="draft")
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/")
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]


class ProductAttributeValue(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="attribute_values")
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT)
    value = models.ForeignKey(AttributeValue, on_delete=models.PROTECT)

    class Meta:
        unique_together = ("product", "attribute", "value")

    def __str__(self):
        return f"{self.product.name}: {self.attribute.name}={self.value.value}"

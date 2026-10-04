from django.conf import settings
from django.db import models


class CustomerProfile(models.Model):
    BUSINESS_TYPE_CHOICES = [
        ("retailer", "Retailer"),
        ("wholesaler", "Wholesaler"),
        ("dealer", "Dealer"),
        ("distributor", "Distributor"),
        ("institution", "Institution"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_profile")
    business_type = models.CharField(max_length=40, choices=BUSINESS_TYPE_CHOICES, default="retailer")
    phone = models.CharField(max_length=30, blank=True)
    gstin = models.CharField(max_length=20, blank=True)
    pan = models.CharField(max_length=20, blank=True)
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=[("active", "Active"), ("pending", "Pending"), ("blocked", "Blocked")], default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username

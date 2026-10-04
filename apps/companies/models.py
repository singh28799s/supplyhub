from django.conf import settings
from django.db import models


class Company(models.Model):
    company_name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=200, blank=True)
    gstin = models.CharField(max_length=30, blank=True)
    pan = models.CharField(max_length=20, blank=True)
    business_type = models.CharField(max_length=80, default="wholesale")
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    verification_status = models.CharField(max_length=20, choices=[("pending", "Pending"), ("verified", "Verified"), ("rejected", "Rejected")], default="pending")
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_terms = models.CharField(max_length=80, blank=True, default="Net 30")
    status = models.CharField(max_length=20, choices=[("active", "Active"), ("inactive", "Inactive")], default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name


class CompanyUser(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="company_users")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_memberships")
    role = models.CharField(max_length=60, default="manager")
    is_primary = models.BooleanField(default=False)

    class Meta:
        unique_together = ("company", "user")

    def __str__(self):
        return f"{self.user} @ {self.company}"


class CompanyAddress(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="addresses")
    address_type = models.CharField(max_length=20, choices=[("billing", "Billing"), ("shipping", "Shipping")], default="billing")
    line1 = models.CharField(max_length=200)
    line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="India")


class BusinessDocument(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=50, default="gst")
    file = models.FileField(upload_to="business_documents/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

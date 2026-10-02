from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Order, Product, QuoteRequest, StoreSettings


class CustomerSignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email address")

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "autocomplete": "username"}
        )
        self.fields["email"].widget.attrs.update(
            {"class": "form-control", "autocomplete": "email"}
        )
        for field_name in ("password1", "password2"):
            self.fields[field_name].widget.attrs.update(
                {"class": "form-control", "autocomplete": "new-password"}
            )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class CustomerAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "autocomplete": "username"}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "form-control", "autocomplete": "current-password"}
        )


class OrderCheckoutForm(forms.ModelForm):
    payment_method = forms.ChoiceField(
        choices=(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Payment method",
    )

    def __init__(self, *args, payment_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_method"].choices = payment_choices or []

    class Meta:
        model = Order
        fields = (
            "customer_name",
            "email",
            "phone",
            "delivery_address",
            "city",
            "postal_code",
            "notes",
            "payment_method",
        )
        labels = {
            "customer_name": "Full name",
            "delivery_address": "Delivery address",
            "postal_code": "PIN / postal code",
            "notes": "Order notes (optional)",
        }
        widgets = {
            "customer_name": forms.TextInput(attrs={"class": "form-control", "autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "autocomplete": "tel"}),
            "delivery_address": forms.Textarea(attrs={"class": "form-control", "rows": 3, "autocomplete": "street-address"}),
            "city": forms.TextInput(attrs={"class": "form-control", "autocomplete": "address-level2"}),
            "postal_code": forms.TextInput(attrs={"class": "form-control", "autocomplete": "postal-code"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class QuoteRequestForm(forms.ModelForm):
    class Meta:
        model = QuoteRequest
        fields = (
            "customer_name",
            "business_name",
            "email",
            "phone",
            "product",
            "quantity",
            "message",
        )
        labels = {
            "customer_name": "Your name",
            "business_name": "Business name (optional)",
            "product": "Product (optional)",
            "quantity": "Required quantity",
            "message": "Requirements / branding details",
        }
        widgets = {
            "customer_name": forms.TextInput(attrs={"class": "form-control", "autocomplete": "name"}),
            "business_name": forms.TextInput(attrs={"class": "form-control", "autocomplete": "organization"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "autocomplete": "tel"}),
            "product": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(
            is_active=True,
            category__is_active=True,
        ).select_related("category")
        self.fields["product"].required = False


class StoreSettingsForm(forms.ModelForm):
    class Meta:
        model = StoreSettings
        fields = (
            "store_name",
            "tagline",
            "support_phone",
            "support_email",
            "address",
            "delivery_note",
        )
        widgets = {
            "store_name": forms.TextInput(attrs={"class": "form-control"}),
            "tagline": forms.TextInput(attrs={"class": "form-control"}),
            "support_phone": forms.TextInput(attrs={"class": "form-control"}),
            "support_email": forms.EmailInput(attrs={"class": "form-control"}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
            "delivery_note": forms.TextInput(attrs={"class": "form-control"}),
        }


class PaymentShippingSettingsForm(forms.ModelForm):
    class Meta:
        model = StoreSettings
        fields = (
            "shipping_charge",
            "free_shipping_threshold",
            "cash_on_delivery_enabled",
            "bank_transfer_enabled",
            "bank_transfer_instructions",
        )
        widgets = {
            "shipping_charge": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "0.01"}),
            "free_shipping_threshold": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "0.01"}),
            "bank_transfer_instructions": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("cash_on_delivery_enabled") and not cleaned_data.get("bank_transfer_enabled"):
            raise forms.ValidationError("Enable at least one offline payment method.")
        return cleaned_data

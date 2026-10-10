import re
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db.models import Q

from .models import (
    PRODUCT_DETAIL_FIELDS,
    Category,
    ProductCustomization,
    Order,
    Product,
    ProductAttribute,
    ProductImage,
    ProductPriceTier,
    QuoteRequest,
    SellerOrder,
    SellerProfile,
    StoreSettings,
)


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


class SellerRegistrationForm(UserCreationForm):
    email = forms.EmailField(label="Business email")
    company_name = forms.CharField(max_length=180)
    contact_name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=30, required=False)
    country = forms.CharField(max_length=100, initial="India")
    city = forms.CharField(max_length=100, required=False)
    business_type = forms.ChoiceField(choices=SellerProfile.BusinessType.choices)
    years_in_business = forms.IntegerField(min_value=0, max_value=200, initial=0)
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["business_type"].widget.attrs["class"] = "form-select"

    def clean_company_name(self):
        company_name = self.cleaned_data["company_name"].strip()
        if SellerProfile.objects.filter(company_name__iexact=company_name).exists():
            raise forms.ValidationError("A seller account already uses this business name.")
        return company_name

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            SellerProfile.objects.create(
                user=user,
                company_name=self.cleaned_data["company_name"],
                contact_name=self.cleaned_data["contact_name"],
                email=self.cleaned_data["email"],
                phone=self.cleaned_data["phone"],
                country=self.cleaned_data["country"],
                city=self.cleaned_data["city"],
                business_type=self.cleaned_data["business_type"],
                years_in_business=self.cleaned_data["years_in_business"],
                description=self.cleaned_data["description"],
            )
        return user


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        clean_one = super().clean
        if isinstance(data, (list, tuple)):
            return [clean_one(item, initial) for item in data]
        return [clean_one(data, initial)]


class SellerProfileForm(forms.ModelForm):
    class Meta:
        model = SellerProfile
        fields = (
            "company_name",
            "contact_name",
            "email",
            "phone",
            "country",
            "city",
            "business_type",
            "years_in_business",
            "description",
            "customization_capabilities",
            "certifications",
            "logo",
            "cover_image",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "customization_capabilities": forms.Textarea(attrs={"rows": 3}),
            "certifications": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["business_type"].widget.attrs["class"] = "form-select"


class SellerProductForm(forms.ModelForm):
    visible_detail_fields = forms.MultipleChoiceField(
        choices=PRODUCT_DETAIL_FIELDS,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Show these details to buyers",
    )
    attributes_text = forms.CharField(
        required=False,
        label="Product specifications",
        help_text="One specification per line, in Name: Value format.",
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "Screen size: 55 inches\nBrand: Your brand"}),
    )
    hidden_attributes = forms.MultipleChoiceField(
        required=False,
        choices=(),
        widget=forms.CheckboxSelectMultiple,
        label="Hide individual specifications",
        help_text="Select any specifications you want to keep private on the product page.",
    )
    price_tiers_text = forms.CharField(
        required=False,
        label="Quantity price tiers",
        help_text="Optional. One per line: 1-99: 120.00 or 100+: 99.00.",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "1-99: 120.00\n100+: 99.00"}),
    )
    customizations_text = forms.CharField(
        required=False,
        label="Customization options",
        help_text="Optional, confirmed separately by quote. One per line: Option | extra price per unit | minimum quantity. Use - if no extra price.",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Custom logo | 5.00 | 100\nCustom packaging | - | 50"}),
    )
    gallery_uploads = MultipleFileField(
        required=False,
        label="Additional product photos",
        help_text="Upload multiple product views. The main image is managed separately.",
    )
    delete_gallery_images = forms.MultipleChoiceField(
        required=False,
        choices=(),
        widget=forms.CheckboxSelectMultiple,
        label="Remove existing gallery photos",
    )

    class Meta:
        model = Product
        fields = (
            "category",
            "name",
            "description",
            "price",
            "offer_price",
            "sample_price",
            "sample_quantity",
            "unit",
            "minimum_order_quantity",
            "track_inventory",
            "stock_quantity",
            "shipping_weight_grams",
            "shipping_length_cm",
            "shipping_width_cm",
            "shipping_height_cm",
            "badge",
            "image",
            "image_url",
            "is_active",
            "visible_detail_fields",
        )
        labels = {
            "track_inventory": "Track available inventory",
            "stock_quantity": "Available units",
            "shipping_weight_grams": "Shipping weight per unit (grams)",
            "shipping_length_cm": "Shipping length per unit (cm)",
            "shipping_width_cm": "Shipping width per unit (cm)",
            "shipping_height_cm": "Shipping height per unit (cm)",
        }
        help_texts = {
            "stock_quantity": "Checkout reserves this quantity when inventory tracking is enabled.",
            "shipping_weight_grams": "Optional product shipping estimate; seller confirms the final packed parcel before Delhivery booking.",
            "shipping_length_cm": "Optional shipping estimate. Enter all four weight/dimension fields together.",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "category": forms.Select(),
            "price": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "offer_price": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "sample_price": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "sample_quantity": forms.NumberInput(attrs={"min": "1"}),
            "minimum_order_quantity": forms.NumberInput(attrs={"min": "1"}),
            "track_inventory": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "stock_quantity": forms.NumberInput(attrs={"min": "0"}),
            "shipping_weight_grams": forms.NumberInput(attrs={"min": "1"}),
            "shipping_length_cm": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "shipping_width_cm": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "shipping_height_cm": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "image_url": forms.URLInput(attrs={"placeholder": "https://"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        self.fields["visible_detail_fields"].choices = PRODUCT_DETAIL_FIELDS
        self.fields["visible_detail_fields"].initial = (
            self.instance.visible_detail_fields
            if self.instance.pk
            else [choice[0] for choice in PRODUCT_DETAIL_FIELDS]
        )
        if self.instance.pk:
            self.fields["attributes_text"].initial = "\n".join(
                f"{attribute.name}: {attribute.value}"
                for attribute in self.instance.attributes.all()
            )
            self.fields["price_tiers_text"].initial = "\n".join(
                (
                    f"{tier.minimum_quantity}-{tier.maximum_quantity}: {tier.unit_price}"
                    if tier.maximum_quantity is not None
                    else f"{tier.minimum_quantity}+: {tier.unit_price}"
                )
                for tier in self.instance.price_tiers.all()
            )
            self.fields["customizations_text"].initial = "\n".join(
                f"{item.name} | {item.additional_unit_price or '-'} | {item.minimum_quantity}"
                for item in self.instance.customizations.all()
            )
            self.fields["delete_gallery_images"].choices = [
                (str(image.pk), image.alt_text or f"Gallery photo {index}")
                for index, image in enumerate(self.instance.gallery_images.all(), start=1)
            ]
            self.fields["hidden_attributes"].choices = [
                (attribute.name, attribute.name)
                for attribute in self.instance.attributes.all()
            ]
            self.fields["hidden_attributes"].initial = [
                attribute.name
                for attribute in self.instance.attributes.filter(is_visible=False)
            ]
        for name, field in self.fields.items():
            if name in {"visible_detail_fields", "is_active"}:
                continue
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["category"].widget.attrs["class"] = "form-select"
        self.fields["visible_detail_fields"].widget.attrs["class"] = "seller-checkbox-widget"
        self.fields["is_active"].widget.attrs["class"] = "form-check-input"
        self.fields["gallery_uploads"].widget.attrs["class"] = "form-control"
        self.fields["delete_gallery_images"].widget.attrs["class"] = "seller-checkbox-widget"
        self.fields["hidden_attributes"].widget.attrs["class"] = "seller-checkbox-widget"
        self.attribute_pairs = []
        self.price_tier_rows = []
        self.customization_rows = []

    def clean_attributes_text(self):
        raw_text = self.cleaned_data.get("attributes_text", "")
        raw_lines = raw_text.splitlines()
        pairs = []
        seen = set()
        for line_number, line in enumerate(raw_lines, start=1):
            if not line.strip():
                continue
            name, separator, value = line.partition(":")
            name = name.strip()
            value = value.strip()
            if not separator or not name or not value:
                raise forms.ValidationError(
                    f"Line {line_number}: enter a specification as Name: Value."
                )
            if name.casefold() in seen:
                raise forms.ValidationError(f"Specification '{name}' is repeated.")
            if len(name) > 100 or len(value) > 250:
                raise forms.ValidationError(
                    f"Line {line_number}: names are limited to 100 characters and values to 250."
                )
            seen.add(name.casefold())
            pairs.append((name, value))
        self.attribute_pairs = pairs
        return raw_text

    def clean_price_tiers_text(self):
        rows = []
        for line_number, line in enumerate(
            self.cleaned_data.get("price_tiers_text", "").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            range_text, separator, price_text = line.partition(":")
            match = re.fullmatch(r"\s*(\d+)(?:\s*-\s*(\d+)|\s*\+)\s*", range_text)
            if not separator or not match:
                raise forms.ValidationError(
                    f"Line {line_number}: use a quantity range such as 1-99 or 100+."
                )
            minimum = int(match.group(1))
            maximum = int(match.group(2)) if match.group(2) else None
            try:
                unit_price = Decimal(price_text.strip())
            except InvalidOperation:
                raise forms.ValidationError(f"Line {line_number}: enter a valid unit price.")
            if minimum < 1 or (maximum is not None and maximum < minimum):
                raise forms.ValidationError(f"Line {line_number}: the quantity range is invalid.")
            if unit_price <= 0:
                raise forms.ValidationError(f"Line {line_number}: the unit price must be positive.")
            if unit_price > Decimal("99999999.99") or unit_price.as_tuple().exponent < -2:
                raise forms.ValidationError(f"Line {line_number}: use up to two decimal places.")
            rows.append((minimum, maximum, unit_price))

        rows.sort(key=lambda row: row[0])
        for index, row in enumerate(rows):
            minimum, maximum = row[0], row[1]
            if index and (
                rows[index - 1][1] is None
                or rows[index - 1][1] >= minimum
            ):
                raise forms.ValidationError("Quantity price tiers must not overlap.")
            if maximum is None and index != len(rows) - 1:
                raise forms.ValidationError("An open-ended price tier must be the last tier.")
        self.price_tier_rows = rows
        return self.cleaned_data.get("price_tiers_text", "")

    def clean_customizations_text(self):
        rows = []
        seen = set()
        for line_number, line in enumerate(
            self.cleaned_data.get("customizations_text", "").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            parts = [part.strip() for part in line.split("|")]
            if len(parts) != 3 or not parts[0]:
                raise forms.ValidationError(
                    f"Line {line_number}: use Option | extra price or - | minimum quantity."
                )
            name, price_text, minimum_text = parts
            if name.casefold() in seen:
                raise forms.ValidationError(f"Customization '{name}' is repeated.")
            if len(name) > 120:
                raise forms.ValidationError(f"Line {line_number}: option names are limited to 120 characters.")
            try:
                additional_price = None if price_text == "-" else Decimal(price_text)
                minimum = int(minimum_text)
            except (InvalidOperation, ValueError):
                raise forms.ValidationError(f"Line {line_number}: enter a valid price and minimum quantity.")
            if additional_price is not None and additional_price < 0:
                raise forms.ValidationError(f"Line {line_number}: extra price cannot be negative.")
            if additional_price is not None and (
                additional_price > Decimal("99999999.99")
                or additional_price.as_tuple().exponent < -2
            ):
                raise forms.ValidationError(f"Line {line_number}: use up to two decimal places.")
            if minimum < 1:
                raise forms.ValidationError(f"Line {line_number}: minimum quantity must be at least 1.")
            seen.add(name.casefold())
            rows.append((name, additional_price, minimum))
        self.customization_rows = rows
        return self.cleaned_data.get("customizations_text", "")

    def clean(self):
        cleaned_data = super().clean()
        offer = cleaned_data.get("offer_price")
        price = cleaned_data.get("price")
        if offer is not None and price is not None and offer >= price:
            self.add_error("offer_price", "Offer price must be lower than the wholesale price.")
        sample_price = cleaned_data.get("sample_price")
        sample_quantity = cleaned_data.get("sample_quantity")
        minimum = cleaned_data.get("minimum_order_quantity")
        if sample_price is not None and sample_quantity is not None and minimum is not None:
            if sample_quantity >= minimum:
                self.add_error(
                    "sample_quantity",
                    "Sample quantity must be below the wholesale minimum order quantity.",
                )
        shipping_fields = (
            "shipping_weight_grams",
            "shipping_length_cm",
            "shipping_width_cm",
            "shipping_height_cm",
        )
        shipping_values = [cleaned_data.get(field) for field in shipping_fields]
        if any(value is not None for value in shipping_values) and not all(
            value is not None for value in shipping_values
        ):
            for field, value in zip(shipping_fields, shipping_values):
                if value is None:
                    self.add_error(field, "Enter all four shipping measurements together.")
        for tier in self.price_tier_rows:
            if minimum is not None and tier[0] < minimum:
                self.add_error(
                    "price_tiers_text",
                    "A price tier cannot start below the minimum order quantity.",
                )
                break
        return cleaned_data

    def save(self, commit=True):
        product = super().save(commit=False)
        product.visible_detail_fields = self.cleaned_data["visible_detail_fields"]
        if commit:
            product.save()
            ProductAttribute.objects.filter(product=product).delete()
            hidden_attributes = set(
                self.cleaned_data.get("hidden_attributes", [])
            )
            ProductAttribute.objects.bulk_create(
                [
                    ProductAttribute(
                        product=product,
                        name=name,
                        value=value,
                        is_visible=name not in hidden_attributes,
                        sort_order=index,
                    )
                    for index, (name, value) in enumerate(self.attribute_pairs)
                ]
            )
            ProductPriceTier.objects.filter(product=product).delete()
            ProductPriceTier.objects.bulk_create(
                [
                    ProductPriceTier(
                        product=product,
                        minimum_quantity=minimum,
                        maximum_quantity=maximum,
                        unit_price=unit_price,
                    )
                    for minimum, maximum, unit_price in self.price_tier_rows
                ]
            )
            ProductCustomization.objects.filter(product=product).delete()
            ProductCustomization.objects.bulk_create(
                [
                    ProductCustomization(
                        product=product,
                        name=name,
                        additional_unit_price=additional_price,
                        minimum_quantity=minimum,
                    )
                    for name, additional_price, minimum in self.customization_rows
                ]
            )
            ProductImage.objects.filter(
                product=product,
                pk__in=self.cleaned_data.get("delete_gallery_images", []),
            ).delete()
            ProductImage.objects.bulk_create(
                [
                    ProductImage(
                        product=product,
                        image=image,
                        alt_text=product.name,
                        sort_order=product.gallery_images.count() + index,
                    )
                    for index, image in enumerate(self.cleaned_data.get("gallery_uploads", []))
                ]
            )
        return product


class SellerOrderStatusForm(forms.ModelForm):
    class Meta:
        model = SellerOrder
        fields = ("status", "seller_notes")
        widgets = {"status": forms.Select(attrs={"class": "form-select"}), "seller_notes": forms.Textarea(attrs={"class": "form-control", "rows": 3})}

    def __init__(self, *args, status_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if status_choices is not None:
            self.fields["status"].choices = status_choices


class DelhiveryShipmentForm(forms.Form):
    package_weight_grams = forms.IntegerField(
        min_value=1,
        label="Packed parcel weight (grams)",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1}),
    )
    package_length_cm = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=7,
        decimal_places=2,
        label="Packed length (cm)",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0.01", "step": "0.01"}),
    )
    package_width_cm = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=7,
        decimal_places=2,
        label="Packed width (cm)",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0.01", "step": "0.01"}),
    )
    package_height_cm = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=7,
        decimal_places=2,
        label="Packed height (cm)",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0.01", "step": "0.01"}),
    )


class SellerQuoteResponseForm(forms.ModelForm):
    class Meta:
        model = QuoteRequest
        fields = ("seller_quoted_unit_price", "seller_response")
        labels = {
            "seller_quoted_unit_price": "Your unit price (optional)",
            "seller_response": "Reply to buyer",
        }
        widgets = {
            "seller_quoted_unit_price": forms.NumberInput(
                attrs={"class": "form-control", "min": "0.01", "step": "0.01"}
            ),
            "seller_response": forms.Textarea(
                attrs={"class": "form-control", "rows": 4}
            ),
        }


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
    seller = forms.ModelChoiceField(
        queryset=SellerProfile.objects.none(),
        required=False,
        widget=forms.HiddenInput,
    )

    class Meta:
        model = QuoteRequest
        fields = (
            "customer_name",
            "business_name",
            "email",
            "phone",
            "product",
            "seller",
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
        ).filter(
            Q(seller__isnull=True)
            | Q(seller__status=SellerProfile.Status.APPROVED, seller__user__is_active=True)
        ).select_related("category", "seller")
        self.fields["seller"].queryset = SellerProfile.objects.filter(
            status=SellerProfile.Status.APPROVED,
            user__is_active=True,
        )
        self.fields["product"].required = False

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        seller = cleaned_data.get("seller")
        if product and product.seller_id:
            if seller and seller != product.seller:
                self.add_error("seller", "The selected product belongs to a different seller.")
            cleaned_data["seller"] = product.seller
        return cleaned_data


class StoreSettingsForm(forms.ModelForm):
    class Meta:
        model = StoreSettings
        fields = (
            "store_name",
            "browser_title",
            "tagline",
            "hero_eyebrow",
            "hero_headline",
            "brand_icon",
            "logo",
            "favicon",
            "primary_color",
            "primary_dark_color",
            "accent_color",
            "page_background_color",
            "text_color",
            "support_phone",
            "support_email",
            "address",
            "delivery_note",
        )
        widgets = {
            "store_name": forms.TextInput(attrs={"class": "form-control"}),
            "browser_title": forms.TextInput(attrs={"class": "form-control"}),
            "tagline": forms.TextInput(attrs={"class": "form-control"}),
            "hero_eyebrow": forms.TextInput(attrs={"class": "form-control"}),
            "hero_headline": forms.TextInput(attrs={"class": "form-control"}),
            "brand_icon": forms.Select(attrs={"class": "form-select"}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "favicon": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "primary_color": forms.TextInput(attrs={"class": "form-control form-control-color", "type": "color"}),
            "primary_dark_color": forms.TextInput(attrs={"class": "form-control form-control-color", "type": "color"}),
            "accent_color": forms.TextInput(attrs={"class": "form-control form-control-color", "type": "color"}),
            "page_background_color": forms.TextInput(attrs={"class": "form-control form-control-color", "type": "color"}),
            "text_color": forms.TextInput(attrs={"class": "form-control form-control-color", "type": "color"}),
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

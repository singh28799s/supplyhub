from django.contrib import admin, messages
from django import forms
from .models import (
    Category,
    Order,
    OrderItem,
    Product,
    ProductAttribute,
    ProductCustomization,
    ProductImage,
    ProductPriceTier,
    PaymentTransaction,
    SellerPayout,
    ShippingEvent,
    PromotionCampaign,
    QuoteRequest,
    SellerOrder,
    SellerProfile,
    StoreSettings,
    Supplier,
)
from .notifications import notify_order_created, notify_order_updated, notify_quote_created, notify_quote_updated
from .inventory import release_order_stock
from .payouts import PayoutNotReadyError, release_seller_payout
from .payments import PaymentGatewayError


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)
    ordering = ("sort_order", "name")


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 0


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class ProductPriceTierInline(admin.TabularInline):
    model = ProductPriceTier
    extra = 0


class ProductCustomizationInline(admin.TabularInline):
    model = ProductCustomization
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "supplier",
        "seller",
        "price",
        "offer_price",
        "sample_price",
        "sample_quantity",
        "track_inventory",
        "stock_quantity",
        "unit",
        "minimum_order_quantity",
        "track_inventory",
        "stock_quantity",
        "is_featured",
        "is_active",
    )
    list_filter = ("category", "is_active", "is_featured")
    list_editable = ("offer_price", "sample_price", "sample_quantity", "is_featured", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description", "category__name")
    autocomplete_fields = ("category", "supplier", "seller")
    inlines = (
        ProductAttributeInline,
        ProductImageInline,
        ProductPriceTierInline,
        ProductCustomizationInline,
    )


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "company_name",
        "contact_name",
        "email",
        "business_type",
        "country",
        "status",
        "created_at",
    )
    list_filter = ("status", "business_type", "country")
    list_editable = ("status",)
    search_fields = ("company_name", "contact_name", "email", "user__username")
    readonly_fields = ("user", "slug", "created_at", "updated_at")
    fieldsets = (
        ("Account review", {"fields": ("user", "status", "review_notes", "razorpay_linked_account_id")}),
        (
            "Public seller profile",
            {
                "fields": (
                    "company_name",
                    "slug",
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
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(SellerOrder)
class SellerOrderAdmin(admin.ModelAdmin):
    list_display = ("order", "seller", "status", "delhivery_status", "created_at", "updated_at")
    list_filter = ("status", "delhivery_status", "created_at")
    search_fields = ("order__reference", "seller__company_name")
    autocomplete_fields = ("order", "seller")
    filter_horizontal = ("items",)
    readonly_fields = (
        "delhivery_shipment_id",
        "delhivery_waybill",
        "delhivery_status",
        "package_weight_grams",
        "package_length_cm",
        "package_width_cm",
        "package_height_cm",
        "shipped_at",
        "delivered_at",
    )


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "provider_order_id",
        "provider_payment_id",
        "status",
        "amount_paise",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("order__reference", "provider_order_id", "provider_payment_id")
    readonly_fields = (
        "order",
        "provider_order_id",
        "provider_payment_id",
        "amount_paise",
        "status",
        "failure_reason",
        "captured_at",
        "created_at",
        "updated_at",
    )


@admin.register(SellerPayout)
class SellerPayoutAdmin(admin.ModelAdmin):
    list_display = (
        "seller_order",
        "gross_amount",
        "commission_amount",
        "net_amount",
        "status",
        "available_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("seller_order__order__reference", "seller_order__seller__company_name")
    readonly_fields = (
        "seller_order",
        "gross_amount",
        "commission_rate",
        "commission_amount",
        "net_amount",
        "available_at",
        "razorpay_transfer_id",
        "failure_reason",
        "created_at",
        "updated_at",
    )
    actions = ("release_selected_payouts",)

    @admin.action(description="Release eligible payouts through Razorpay Route")
    def release_selected_payouts(self, request, queryset):
        for payout in queryset:
            try:
                transfer_id = release_seller_payout(payout.pk)
            except (PayoutNotReadyError, PaymentGatewayError) as exc:
                self.message_user(
                    request,
                    f"Payout {payout.pk} was not released: {exc}",
                    level=messages.ERROR,
                )
            else:
                self.message_user(
                    request,
                    f"Payout {payout.pk} submitted to Razorpay as {transfer_id}.",
                    level=messages.SUCCESS,
                )


@admin.register(ShippingEvent)
class ShippingEventAdmin(admin.ModelAdmin):
    list_display = ("seller_order", "status", "occurred_at", "created_at")
    list_filter = ("status", "created_at")
    search_fields = (
        "seller_order__order__reference",
        "seller_order__seller__company_name",
        "status",
    )


@admin.register(PromotionCampaign)
class PromotionCampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "headline", "is_active", "starts_at", "ends_at", "sort_order")
    list_filter = ("is_active", "button_target", "starts_at", "ends_at")
    list_editable = ("is_active", "sort_order")
    search_fields = ("name", "headline", "description")
    autocomplete_fields = ("product",)
    fieldsets = (
        ("Campaign content", {"fields": ("name", "eyebrow", "headline", "description", "image")}),
        ("Call to action", {"fields": ("button_label", "button_target", "product")}),
        ("Schedule and display", {"fields": ("is_active", "starts_at", "ends_at", "sort_order")}),
    )


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_name", "unit", "unit_price", "quantity", "is_sample")
    can_delete = False


class OrderAdminForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        cancel_requested = (
            cleaned_data.get("status") == Order.Status.CANCELLED
            and self.instance.status != Order.Status.CANCELLED
        )
        if cleaned_data.get("payment_status") == Order.PaymentStatus.REFUNDED and cleaned_data.get("payment_received"):
            self.add_error(
                "payment_received",
                "Uncheck this after confirming the refund in the payment provider.",
            )
        if (
            cancel_requested
            and self.instance.payment_received
            and cleaned_data.get("payment_status") != Order.PaymentStatus.REFUNDED
        ):
            self.add_error(
                "status",
                "Refund the captured payment and mark it Refunded before cancelling this order.",
            )
        if self.instance.pk and cancel_requested:
            transfer_exists = self.instance.seller_orders.filter(
                payout__razorpay_transfer_id__isnull=False
            ).exists()
            if transfer_exists:
                self.add_error(
                    "status",
                    "A seller transfer was submitted. Reconcile the Razorpay transfer before cancelling.",
                )
        return cleaned_data


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_name", "email", "total_amount", "status", "payment_method", "payment_status", "payment_received", "created_at")
    list_filter = ("status", "payment_method", "payment_status", "payment_received", "created_at")
    search_fields = ("=id", "reference", "customer_name", "email", "phone")
    readonly_fields = ("reference", "created_at", "total_amount")
    inlines = (OrderItemInline,)
    form = OrderAdminForm

    def save_model(self, request, obj, form, change):
        previous = None
        if change:
            previous = Order.objects.filter(pk=obj.pk).values(
                "status",
                "payment_received",
            ).first()
        if (
            obj.payment_method != Order.PaymentMethod.RAZORPAY
            and obj.payment_status != Order.PaymentStatus.REFUNDED
        ):
            obj.payment_status = (
                Order.PaymentStatus.CAPTURED
                if obj.payment_received
                else Order.PaymentStatus.OFFLINE_PENDING
            )
        super().save_model(request, obj, form, change)
        if previous and previous["status"] != obj.status and obj.status == Order.Status.CANCELLED:
            release_order_stock(obj.pk)
        if not change:
            notify_order_created(obj.pk)
        elif previous:
            changed_fields = [
                field
                for field in ("status", "payment_received")
                if previous[field] != getattr(obj, field)
            ]
            if changed_fields:
                notify_order_updated(obj.pk, changed_fields)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("company_name", "contact_name", "email", "phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("company_name", "contact_name", "email", "phone", "gstin")


@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    list_display = ("reference", "customer_name", "business_name", "product_name", "quantity", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("reference", "customer_name", "business_name", "email", "phone", "product_name")
    readonly_fields = ("reference", "product", "product_name", "quantity", "customer", "created_at", "updated_at")
    autocomplete_fields = ("seller",)

    def save_model(self, request, obj, form, change):
        previous = None
        if change:
            previous = QuoteRequest.objects.filter(pk=obj.pk).values(
                "status",
                "quoted_unit_price",
                "admin_response",
                "seller_quoted_unit_price",
                "seller_response",
            ).first()
        super().save_model(request, obj, form, change)
        if not change:
            notify_quote_created(obj.pk)
        elif previous:
            changed_fields = [
                field
                for field in (
                    "status",
                    "quoted_unit_price",
                    "admin_response",
                    "seller_quoted_unit_price",
                    "seller_response",
                )
                if previous[field] != getattr(obj, field)
            ]
            if changed_fields:
                notify_quote_updated(obj.pk, changed_fields)


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not StoreSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

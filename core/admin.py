from django.contrib import admin
from .models import Category, Order, OrderItem, Product, QuoteRequest, StoreSettings, Supplier
from .notifications import notify_order_created, notify_order_updated, notify_quote_created, notify_quote_updated


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)
    ordering = ("sort_order", "name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "supplier",
        "price",
        "offer_price",
        "sample_price",
        "sample_quantity",
        "unit",
        "minimum_order_quantity",
        "is_featured",
        "is_active",
    )
    list_filter = ("category", "is_active", "is_featured")
    list_editable = ("offer_price", "sample_price", "sample_quantity", "is_featured", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description", "category__name")
    autocomplete_fields = ("category", "supplier")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_name", "unit", "unit_price", "quantity", "is_sample")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "customer_name", "email", "total_amount", "status", "payment_method", "payment_received", "created_at")
    list_filter = ("status", "payment_method", "payment_received", "created_at")
    search_fields = ("reference", "customer_name", "email", "phone")
    readonly_fields = ("reference", "created_at", "total_amount")
    inlines = (OrderItemInline,)

    def save_model(self, request, obj, form, change):
        previous = None
        if change:
            previous = Order.objects.filter(pk=obj.pk).values(
                "status",
                "payment_received",
            ).first()
        super().save_model(request, obj, form, change)
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

    def save_model(self, request, obj, form, change):
        previous = None
        if change:
            previous = QuoteRequest.objects.filter(pk=obj.pk).values(
                "status",
                "quoted_unit_price",
                "admin_response",
            ).first()
        super().save_model(request, obj, form, change)
        if not change:
            notify_quote_created(obj.pk)
        elif previous:
            changed_fields = [
                field
                for field in ("status", "quoted_unit_price", "admin_response")
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

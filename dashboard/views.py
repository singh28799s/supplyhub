from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import PaymentShippingSettingsForm, StoreSettingsForm
from core.models import (
    Category,
    Order,
    Product,
    PromotionCampaign,
    QuoteRequest,
    SellerPayout,
    SellerProfile,
    StoreSettings,
    Supplier,
)


@staff_member_required(login_url="admin:login")
def index(request):
    today = timezone.localdate()
    store_settings = StoreSettings.load()
    form_type = request.POST.get("form_type", "")
    brand_form = StoreSettingsForm(
        request.POST if form_type == "store" else None,
        request.FILES if form_type == "store" else None,
        instance=store_settings,
        prefix="store",
    )
    shipping_form = PaymentShippingSettingsForm(
        request.POST if form_type == "shipping" else None,
        instance=store_settings,
        prefix="shipping",
    )

    if request.method == "POST":
        form = brand_form if form_type == "store" else shipping_form
        if form_type in {"store", "shipping"} and form.is_valid():
            form.save()
            messages.success(request, "Store settings saved.")
            return redirect("dashboard:index")
        if form_type not in {"store", "shipping"}:
            messages.error(request, "Unknown settings form.")

    context = {
        "category_count": Category.objects.filter(is_active=True).count(),
        "product_count": Product.objects.filter(is_active=True).count(),
        "order_count": Order.objects.count(),
        "pending_order_count": Order.objects.filter(status=Order.Status.PENDING).count(),
        "today_order_count": Order.objects.filter(created_at__date=today).count(),
        "customer_count": get_user_model().objects.filter(is_staff=False, is_superuser=False).count(),
        "customers": get_user_model().objects.filter(
            is_staff=False,
            is_superuser=False,
        ).annotate(
            customer_order_count=Count("supplyhub_orders", distinct=True),
            customer_total=Sum("supplyhub_orders__total_amount"),
        ).order_by("username"),
        "seller_profiles": SellerProfile.objects.filter(
            status__in=[
                SellerProfile.Status.PENDING,
                SellerProfile.Status.REJECTED,
            ]
        ).select_related("user").annotate(
            product_count=Count("products", distinct=True)
        ),
        "pending_seller_count": SellerProfile.objects.filter(
            status=SellerProfile.Status.PENDING
        ).count(),
        "categories": Category.objects.filter(is_active=True).annotate(
            product_count=Count("products", filter=Q(products__is_active=True))
        ),
        "total_sales": Order.objects.exclude(status=Order.Status.CANCELLED).aggregate(
            total=Sum("total_amount")
        )["total"] or 0,
        "recent_orders": Order.objects.annotate(item_count=Count("items", distinct=True))[:8],
        "products": Product.objects.select_related(
            "category",
            "seller__user",
        ).order_by("name"),
        "orders": Order.objects.annotate(item_count=Count("items", distinct=True)),
        "quotes": QuoteRequest.objects.all(),
        "quote_count": QuoteRequest.objects.count(),
        "pending_quote_count": QuoteRequest.objects.filter(status=QuoteRequest.Status.PENDING).count(),
        "ready_payout_count": SellerPayout.objects.filter(
            status=SellerPayout.Status.READY
        ).count(),
        "campaign_count": PromotionCampaign.objects.count(),
        "active_campaign_count": PromotionCampaign.active_now().count(),
        "active_campaign_ids": set(PromotionCampaign.active_now().values_list("pk", flat=True)),
        "campaigns": PromotionCampaign.objects.select_related("product"),
        "suppliers": Supplier.objects.annotate(product_count=Count("products", distinct=True)),
        "supplier_count": Supplier.objects.count(),
        "offer_products": Product.objects.filter(
            is_active=True,
            offer_price__isnull=False,
        ).select_related("category"),
        "store_settings": store_settings,
        "brand_form": brand_form,
        "shipping_form": shipping_form,
        "form_error_page": (
            {"store": "settings", "shipping": "payment"}.get(form_type, "")
            if request.method == "POST"
            else ""
        ),
    }
    return render(request, "dashboard/index.html", context)


@staff_member_required(login_url="admin:login")
@require_POST
def seller_status_update(request, seller_id):
    seller = get_object_or_404(
        SellerProfile.objects.select_related("user"),
        pk=seller_id,
    )
    action = request.POST.get("action")

    if action == "approve":
        if not seller.user.is_active:
            messages.error(
                request,
                f"{seller.company_name} cannot be approved while its account is disabled.",
            )
            return redirect("dashboard:index")
        with transaction.atomic():
            seller.status = SellerProfile.Status.APPROVED
            seller.save(update_fields=["status", "updated_at"])
            published_count = Product.objects.filter(seller=seller).update(
                is_active=True,
                updated_at=timezone.now(),
            )
        messages.success(
            request,
            f"{seller.company_name} approved; {published_count} product(s) published.",
        )
    elif action == "reject":
        with transaction.atomic():
            seller.status = SellerProfile.Status.REJECTED
            seller.save(update_fields=["status", "updated_at"])
            Product.objects.filter(seller=seller).update(
                is_active=False,
                updated_at=timezone.now(),
            )
        messages.success(request, f"{seller.company_name} application rejected.")
    else:
        messages.error(request, "Choose a valid seller review action.")

    return redirect("dashboard:index")

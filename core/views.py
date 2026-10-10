import json
from decimal import Decimal
from datetime import timedelta
from functools import wraps

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import (
    CustomerSignUpForm,
    DelhiveryShipmentForm,
    OrderCheckoutForm,
    QuoteRequestForm,
    SellerOrderStatusForm,
    SellerProfileForm,
    SellerProductForm,
    SellerQuoteResponseForm,
    SellerRegistrationForm,
)
from .models import (
    Category,
    Order,
    OrderItem,
    Product,
    PaymentTransaction,
    PaymentWebhookEvent,
    PromotionCampaign,
    QuoteRequest,
    SellerOrder,
    SellerPayout,
    SellerProfile,
    StoreSettings,
)
from .notifications import (
    notify_order_created,
    notify_order_cancelled,
    notify_order_updated,
    notify_quote_created,
    notify_quote_updated,
    notify_seller_order_updated,
)
from .inventory import release_order_stock, reserve_stock
from .payments import (
    PaymentGatewayError,
    create_provider_order,
    fetch_payment,
    razorpay_is_configured,
    verify_checkout_signature,
    verify_webhook_signature,
)
from .shipping import DelhiveryError, create_shipment, delhivery_is_configured, fetch_tracking


def public_product_filter():
    return (
        Q(seller__isnull=True)
        | Q(
            seller__status=SellerProfile.Status.APPROVED,
            seller__user__is_active=True,
        )
    )


def public_products():
    return (
        Product.objects.filter(is_active=True, category__is_active=True)
        .filter(public_product_filter())
        .select_related("category", "seller")
        .prefetch_related("price_tiers")
    )


def seller_account_required(view):
    @wraps(view)
    @login_required(login_url="login")
    def wrapped(request, *args, **kwargs):
        if not SellerProfile.objects.filter(user=request.user).exists():
            messages.error(request, "Apply for a seller account to open the seller portal.")
            return redirect("seller_register")
        return view(request, *args, **kwargs)

    return wrapped


def _cart_rows(request):
    cart = request.session.get("cart", {})
    products = public_products().filter(pk__in=cart)
    rows = []
    clean_cart = {}
    total = Decimal("0.00")

    for product in products:
        quantity = cart.get(str(product.pk), 0)
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            continue
        if quantity < 1:
            continue
        if not product.is_directly_orderable:
            continue
        clean_cart[str(product.pk)] = quantity
        unit_price = product.unit_price_for_quantity(quantity)
        is_sample = product.sample_price is not None and quantity == product.sample_quantity
        line_total = unit_price * quantity
        total += line_total
        rows.append(
            {
                "product": product,
                "quantity": quantity,
                "unit_price": unit_price,
                "is_sample": is_sample,
                "cart_minimum": (
                    product.sample_quantity
                    if product.sample_price is not None
                    else product.minimum_order_quantity
                ),
                "line_total": line_total,
            }
        )

    if clean_cart != cart:
        request.session["cart"] = clean_cart

    return rows, total


def home(request):
    store_settings = StoreSettings.load()
    categories = Category.objects.filter(is_active=True).annotate(
        product_count=Count(
            "products",
            filter=Q(products__is_active=True)
            & (
                Q(products__seller__isnull=True)
                | Q(
                    products__seller__status=SellerProfile.Status.APPROVED,
                    products__seller__user__is_active=True,
                )
            ),
        )
    )
    products = public_products().select_related("category")
    promotional_products = products.filter(
        Q(offer_price__lt=F("price")) | Q(sample_price__isnull=False)
    )
    wishlist_ids = request.session.get("wishlist", [])

    return render(
        request,
        "core/home.html",
        {
            "categories": categories,
            "product_categories": categories.filter(product_count__gt=0),
            "products": products,
            "featured_products": products.filter(is_featured=True)[:8],
            "new_products": products.order_by("-created_at")[:8],
            "offer_products": promotional_products.order_by("-is_featured", "name")[:8],
            "campaigns": PromotionCampaign.active_now().select_related("product"),
            "cart_count": sum(request.session.get("cart", {}).values()),
            "wishlist_ids": wishlist_ids,
            "store_settings": store_settings,
        },
    )


def product_detail(request, slug):
    product = get_object_or_404(
        public_products().prefetch_related(
            "gallery_images",
            "attributes",
            "customizations",
        ),
        slug=slug,
    )
    store_settings = StoreSettings.load()
    return render(
        request,
        "core/product_detail.html",
        {
            "product": product,
            "seller": product.seller,
            "store_settings": store_settings,
            "cart_count": sum(request.session.get("cart", {}).values()),
        },
    )


def quote_request(request):
    initial = {}
    product_id = request.GET.get("product")
    if product_id:
        initial["product"] = product_id
    seller_slug = request.GET.get("seller")
    if seller_slug:
        initial["seller"] = get_object_or_404(
            SellerProfile,
            slug=seller_slug,
            status=SellerProfile.Status.APPROVED,
            user__is_active=True,
        ).pk
    form = QuoteRequestForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        quote = form.save(commit=False)
        quote.customer = request.user if request.user.is_authenticated else None
        quote.product_name = quote.product.name if quote.product else "General wholesale request"
        quote.save()
        notify_quote_created(quote.pk)
        return redirect("quote_confirmation", reference=quote.reference)
    return render(request, "core/quote_request.html", {"form": form})


def quote_confirmation(request, reference):
    quote = get_object_or_404(QuoteRequest, reference=reference)
    if quote.customer_id and quote.customer_id != request.user.pk:
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    return render(request, "core/quote_confirmation.html", {"quote": quote})


@login_required(login_url="login")
def my_quotes(request):
    quotes = QuoteRequest.objects.filter(customer=request.user)
    return render(request, "core/my_quotes.html", {"quotes": quotes})


@require_POST
def add_to_cart(request):
    product = get_object_or_404(
        public_products(),
        pk=request.POST.get("product_id"),
    )
    if not product.is_directly_orderable:
        return JsonResponse(
            {
                "ok": False,
                "message": f"{product.name}: the seller has set pricing to quote-only. Request a quote instead.",
            },
            status=400,
        )
    try:
        quantity = int(request.POST.get("quantity", product.minimum_order_quantity))
    except (TypeError, ValueError):
        quantity = product.minimum_order_quantity

    if quantity < 1:
        return JsonResponse({"ok": False, "message": f"{product.name}: quantity must be at least 1."}, status=400)

    if product.sample_price is not None and quantity == product.sample_quantity:
        allowed_quantity = product.sample_quantity
    else:
        allowed_quantity = product.minimum_order_quantity

    if quantity < allowed_quantity:
        minimum_text = (
            f"{product.sample_quantity} sample units"
            if product.sample_price is not None and product.sample_quantity > 0
            else f"{product.minimum_order_quantity}"
        )
        return JsonResponse(
            {"ok": False, "message": f"{product.name}: minimum order is {minimum_text} {product.unit}."},
            status=400,
        )

    cart = request.session.get("cart", {})
    product_key = str(product.pk)
    cart_quantity = int(cart.get(product_key, 0)) + quantity
    if product.track_inventory and cart_quantity > product.stock_quantity:
        return JsonResponse(
            {
                "ok": False,
                "message": f"{product.name} has only {product.stock_quantity} units available.",
            },
            status=400,
        )
    cart[product_key] = cart_quantity
    request.session["cart"] = cart
    count = sum(cart.values())
    return JsonResponse({"ok": True, "cart_count": count, "message": f"{product.name} added to cart"})


@require_POST
def buy_now(request, product_id):
    product = get_object_or_404(
        public_products(),
        pk=product_id,
    )
    if not product.is_directly_orderable:
        messages.info(request, "This seller provides pricing by quote only.")
        return redirect("product_detail", slug=product.slug)
    try:
        quantity = int(request.POST.get("quantity", product.minimum_order_quantity))
    except (TypeError, ValueError):
        quantity = product.minimum_order_quantity

    minimum_quantity = product.sample_quantity if product.sample_price is not None and quantity == product.sample_quantity else product.minimum_order_quantity
    if quantity < minimum_quantity:
        unit_label = "" if product.sample_price is None else f" or sample quantity {product.sample_quantity}"
        messages.error(request, f"{product.name}: minimum order is {minimum_quantity}{unit_label} {product.unit}.")
        return redirect("product_detail", slug=product.slug)
    if product.track_inventory and quantity > product.stock_quantity:
        messages.error(
            request,
            f"{product.name} has only {product.stock_quantity} units available.",
        )
        return redirect("product_detail", slug=product.slug)

    request.session["cart"] = {str(product.pk): quantity}
    return redirect("checkout")


@require_POST
def buy_sample(request, product_id):
    product = get_object_or_404(
        public_products(),
        pk=product_id,
    )
    if not product.is_directly_orderable:
        messages.info(request, "This seller provides pricing by quote only.")
        return redirect("product_detail", slug=product.slug)
    if product.sample_price is None:
        messages.error(request, "A sample is not available for this product.")
        return redirect("home")
    if product.track_inventory and product.sample_quantity > product.stock_quantity:
        messages.error(
            request,
            f"{product.name} has only {product.stock_quantity} units available.",
        )
        return redirect("product_detail", slug=product.slug)
    request.session["cart"] = {str(product.pk): product.sample_quantity}
    return redirect("checkout")


@require_POST
def toggle_wishlist(request):
    product = get_object_or_404(
        public_products(),
        pk=request.POST.get("product_id"),
    )
    wishlist = request.session.get("wishlist", [])
    product_id = str(product.pk)
    if product_id in wishlist:
        wishlist.remove(product_id)
        added = False
    else:
        wishlist.append(product_id)
        added = True
    request.session["wishlist"] = wishlist
    return JsonResponse(
        {
            "ok": True,
            "added": added,
            "wishlist_count": len(wishlist),
            "message": f"{product.name} {'added to' if added else 'removed from'} wishlist",
        }
    )


def wishlist_detail(request):
    wishlist_ids = request.session.get("wishlist", [])
    products = public_products().filter(pk__in=wishlist_ids)
    return render(
        request,
        "core/wishlist.html",
        {"wishlist_products": products, "wishlist_ids": wishlist_ids},
    )


def cart_detail(request):
    rows, total = _cart_rows(request)
    store_settings = StoreSettings.load()
    shipping_charge = store_settings.shipping_for_subtotal(total)
    return render(
        request,
        "core/cart.html",
        {
            "cart_rows": rows,
            "cart_subtotal": total,
            "shipping_charge": shipping_charge,
            "cart_total": total + shipping_charge,
        },
    )


@require_POST
def update_cart(request, product_id):
    product = get_object_or_404(public_products(), pk=product_id)
    cart = request.session.get("cart", {})
    product_key = str(product.pk)
    action = request.POST.get("action")

    if action == "remove":
        cart.pop(product_key, None)
        messages.success(request, f"{product.name} removed from your cart.")
    elif action == "update":
        if not product.is_directly_orderable:
            cart.pop(product_key, None)
            messages.error(request, "This product is now quote-only and was removed from your cart.")
            request.session["cart"] = cart
            return redirect("cart")
        try:
            quantity = int(request.POST.get("quantity", ""))
        except (TypeError, ValueError):
            messages.error(request, "Enter a valid whole-number quantity.")
        else:
            is_sample_quantity = (
                product.sample_price is not None
                and quantity == product.sample_quantity
            )
            if quantity < 1 or (
                not is_sample_quantity
                and quantity < product.minimum_order_quantity
            ):
                minimum_or_sample = (
                    f"{product.sample_quantity} sample at ₹{product.sample_price}, or "
                    f"{product.minimum_order_quantity}+ for wholesale"
                    if product.sample_price is not None
                    else f"minimum wholesale order is {product.minimum_order_quantity}"
                )
                messages.error(
                    request,
                    f"{product.name}: {minimum_or_sample} {product.unit}.",
                )
            else:
                if product.track_inventory and quantity > product.stock_quantity:
                    messages.error(
                        request,
                        f"{product.name} has only {product.stock_quantity} units available.",
                    )
                else:
                    cart[product_key] = quantity
                    messages.success(request, "Cart quantity updated.")
    else:
        messages.error(request, "That cart action is not supported.")

    request.session["cart"] = cart
    return redirect("cart")


def checkout(request):
    cart_rows, subtotal = _cart_rows(request)
    if not cart_rows:
        messages.info(request, "Your cart is empty. Add a product before checkout.")
        return redirect("cart")

    store_settings = StoreSettings.load()
    shipping_charge = store_settings.shipping_for_subtotal(subtotal)
    payment_choices = []
    if store_settings.cash_on_delivery_enabled:
        payment_choices.append((Order.PaymentMethod.CASH_ON_DELIVERY, "Cash on delivery"))
    if store_settings.bank_transfer_enabled:
        payment_choices.append((Order.PaymentMethod.BANK_TRANSFER, "Bank transfer"))
    if razorpay_is_configured():
        payment_choices.append((Order.PaymentMethod.RAZORPAY, "Pay online with Razorpay"))
    form = OrderCheckoutForm(
        request.POST or None,
        payment_choices=payment_choices,
    )
    if request.method == "POST" and form.is_valid():
        cart = request.session.get("cart", {})
        gateway_order_id = None
        checkout_order = form.save(commit=False)
        if checkout_order.payment_method == Order.PaymentMethod.RAZORPAY:
            try:
                gateway_order_id = create_provider_order(
                    subtotal + shipping_charge,
                    str(checkout_order.reference),
                )
            except PaymentGatewayError as exc:
                messages.error(request, str(exc))
                return render(
                    request,
                    "core/checkout.html",
                    {
                        "form": form,
                        "cart_rows": cart_rows,
                        "cart_subtotal": subtotal,
                        "cart_total": subtotal + shipping_charge,
                        "shipping_charge": shipping_charge,
                        "store_settings": store_settings,
                        "razorpay_available": razorpay_is_configured(),
                    },
                    status=503,
                )
        with transaction.atomic():
            product_ids = [int(product_id) for product_id in cart]
            locked_products = (
                Product.objects.select_for_update()
                .filter(pk__in=product_ids, is_active=True, category__is_active=True)
                .filter(public_product_filter())
                .select_related("seller__user")
                .prefetch_related("price_tiers")
            )
            products = {product.pk: product for product in locked_products}
            if len(products) != len(product_ids):
                messages.error(request, "A product in your cart is no longer available. Please review your cart.")
                return redirect("cart")

            for product_id, raw_quantity in cart.items():
                product = products[int(product_id)]
                quantity = int(raw_quantity)
                is_sample_quantity = (
                    product.sample_price is not None
                    and quantity == product.sample_quantity
                )
                if quantity < 1 or (
                    not is_sample_quantity
                    and quantity < product.minimum_order_quantity
                ):
                    messages.error(
                        request,
                        f"{product.name} quantity must be {product.sample_quantity} sample or at least {product.minimum_order_quantity} for wholesale.",
                    )
                    return redirect("cart")
                if product.track_inventory and quantity > product.stock_quantity:
                    messages.error(
                        request,
                        f"{product.name} has only {product.stock_quantity} units available.",
                    )
                    return redirect("cart")

            current_subtotal = sum(
                (
                    products[int(product_id)].unit_price_for_quantity(int(quantity))
                    * int(quantity)
                    for product_id, quantity in cart.items()
                ),
                Decimal("0.00"),
            )
            if gateway_order_id and current_subtotal + shipping_charge != subtotal + shipping_charge:
                messages.error(
                    request,
                    "A product price changed during checkout. Please review your cart and try again.",
                )
                return redirect("cart")

            order = checkout_order
            order.shipping_charge = shipping_charge
            if gateway_order_id:
                order.payment_status = Order.PaymentStatus.PENDING
            else:
                order.payment_status = Order.PaymentStatus.OFFLINE_PENDING
            if request.user.is_authenticated:
                order.customer = request.user
            order.save()
            total = Decimal("0.00")
            seller_items = {}
            for product_id, raw_quantity in cart.items():
                product = products[int(product_id)]
                quantity = int(raw_quantity)
                unit_price = product.unit_price_for_quantity(quantity)
                is_sample = (
                    product.sample_price is not None
                    and quantity == product.sample_quantity
                )
                reserve_stock(product, quantity)
                order_item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    unit=product.unit,
                    unit_price=unit_price,
                    quantity=quantity,
                    is_sample=is_sample,
                    stock_reserved=product.track_inventory,
                )
                if product.seller_id and product.seller.is_approved:
                    seller_items.setdefault(product.seller, []).append(order_item)
                total += unit_price * quantity
            for seller, seller_order_items in seller_items.items():
                seller_order = SellerOrder.objects.create(order=order, seller=seller)
                seller_order.items.set(seller_order_items)
            order.total_amount = total + order.shipping_charge
            order.save(update_fields=["total_amount"])
            if gateway_order_id:
                PaymentTransaction.objects.create(
                    order=order,
                    provider_order_id=gateway_order_id,
                    amount_paise=int(order.total_amount * 100),
                )
            else:
                notify_order_created(order.pk)

        request.session["cart"] = {}
        if gateway_order_id:
            return render(
                request,
                "core/payment_checkout.html",
                {
                    "order": order,
                    "provider_order_id": gateway_order_id,
                    "razorpay_key_id": settings.RAZORPAY_KEY_ID,
                    "amount_paise": int(order.total_amount * 100),
                },
            )
        return redirect("order_confirmation", reference=order.reference)

    return render(
        request,
        "core/checkout.html",
        {
            "form": form,
            "cart_rows": cart_rows,
            "cart_subtotal": sum((row["line_total"] for row in cart_rows), Decimal("0.00")),
            "cart_total": subtotal + shipping_charge,
            "shipping_charge": shipping_charge,
            "store_settings": store_settings,
            "razorpay_available": razorpay_is_configured(),
        },
    )


def _mark_payment_captured(payment_transaction, payment_id):
    with transaction.atomic():
        payment_transaction = (
            PaymentTransaction.objects.select_for_update()
            .select_related("order")
            .get(pk=payment_transaction.pk)
        )
        order = Order.objects.select_for_update().get(pk=payment_transaction.order_id)
        if payment_transaction.status == PaymentTransaction.Status.CAPTURED:
            if payment_transaction.provider_payment_id != payment_id:
                raise PaymentGatewayError(
                    "This Razorpay order has already been settled by a different payment."
                )
            return order

        payment_transaction.provider_payment_id = payment_id
        payment_transaction.status = PaymentTransaction.Status.CAPTURED
        payment_transaction.captured_at = timezone.now()
        payment_transaction.save(
            update_fields=[
                "provider_payment_id",
                "status",
                "captured_at",
                "updated_at",
            ]
        )
        order.payment_status = Order.PaymentStatus.CAPTURED
        order.payment_received = True
        order.save(update_fields=["payment_status", "payment_received"])

        commission_rate = Decimal(settings.SUPPLYHUB_SELLER_COMMISSION_PERCENT)
        for seller_order in order.seller_orders.select_related("seller").prefetch_related("items"):
            gross = seller_order.subtotal.quantize(Decimal("0.01"))
            commission = (gross * commission_rate / Decimal("100")).quantize(
                Decimal("0.01")
            )
            SellerPayout.objects.get_or_create(
                seller_order=seller_order,
                defaults={
                    "gross_amount": gross,
                    "commission_rate": commission_rate,
                    "commission_amount": commission,
                    "net_amount": gross - commission,
                    "available_at": (
                        seller_order.delivered_at
                        + timedelta(days=settings.SUPPLYHUB_PAYOUT_HOLD_DAYS)
                        if seller_order.delivered_at
                        else None
                    ),
                    "status": (
                        SellerPayout.Status.READY
                        if seller_order.delivered_at
                        and seller_order.delivered_at
                        + timedelta(days=settings.SUPPLYHUB_PAYOUT_HOLD_DAYS)
                        <= timezone.now()
                        else SellerPayout.Status.HOLD
                        if seller_order.delivered_at
                        else SellerPayout.Status.WAITING_DELIVERY
                    ),
                },
            )
        transaction.on_commit(lambda: notify_order_created(order.pk))
        return order


@require_POST
def razorpay_verify(request):
    try:
        data = json.loads(request.body)
        provider_order_id = data["razorpay_order_id"]
        payment_id = data["razorpay_payment_id"]
        signature = data["razorpay_signature"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return JsonResponse({"ok": False, "message": "Invalid payment response."}, status=400)

    if not verify_checkout_signature(provider_order_id, payment_id, signature):
        return JsonResponse({"ok": False, "message": "Payment signature verification failed."}, status=400)
    payment_transaction = get_object_or_404(
        PaymentTransaction.objects.select_related("order"),
        provider_order_id=provider_order_id,
    )
    try:
        provider_payment = fetch_payment(payment_id)
    except PaymentGatewayError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=503)
    if (
        provider_payment.get("order_id") != provider_order_id
        or provider_payment.get("status") != "captured"
        or provider_payment.get("amount") != payment_transaction.amount_paise
    ):
        return JsonResponse(
            {"ok": False, "message": "Razorpay has not confirmed the full captured payment."},
            status=400,
        )

    try:
        order = _mark_payment_captured(payment_transaction, payment_id)
    except PaymentGatewayError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=409)
    return JsonResponse(
        {
            "ok": True,
            "redirect_url": reverse(
                "order_confirmation",
                kwargs={"reference": order.reference},
            ),
        }
    )


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    signature = request.headers.get("X-Razorpay-Signature", "")
    event_id = request.headers.get("X-Razorpay-Event-Id", "")
    if not event_id or not verify_webhook_signature(request.body, signature):
        return HttpResponse(status=400)
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    event_type = payload.get("event", "")
    payment_transaction = None
    payment = {}
    transfer = {}
    if event_type == "payment.captured":
        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        try:
            payment_transaction = PaymentTransaction.objects.get(
                provider_order_id=payment["order_id"],
                amount_paise=payment["amount"],
            )
        except (PaymentTransaction.DoesNotExist, KeyError, TypeError):
            return HttpResponse(status=400)
        if payment.get("status") != "captured" or not payment.get("id"):
            return HttpResponse(status=400)
    elif event_type in {"transfer.processed", "transfer.failed"}:
        transfer = payload.get("payload", {}).get("transfer", {}).get("entity", {})
        if not transfer.get("id"):
            return HttpResponse(status=400)

    with transaction.atomic():
        _, created = PaymentWebhookEvent.objects.get_or_create(
            provider_event_id=event_id,
            defaults={"event_type": event_type},
        )
        if not created:
            return HttpResponse(status=200)

        if event_type == "payment.captured":
            _mark_payment_captured(payment_transaction, payment["id"])
        elif event_type in {"transfer.processed", "transfer.failed"}:
            payout = SellerPayout.objects.select_for_update().filter(
                razorpay_transfer_id=transfer.get("id")
            ).first()
            if payout is None:
                seller_order_id = (
                    transfer.get("notes", {}).get("supplyhub_seller_order")
                )
                if seller_order_id:
                    payout = SellerPayout.objects.select_for_update().filter(
                        seller_order_id=seller_order_id,
                        status=SellerPayout.Status.PROCESSING,
                        razorpay_transfer_id__isnull=True,
                    ).first()
            if payout:
                payout.razorpay_transfer_id = transfer["id"]
                payout.status = (
                    SellerPayout.Status.PAID
                    if event_type == "transfer.processed"
                    else SellerPayout.Status.FAILED
                )
                payout.failure_reason = (
                    transfer.get("failure_reason", "")
                    if event_type == "transfer.failed"
                    else ""
                )
                payout.save(
                    update_fields=[
                        "razorpay_transfer_id",
                        "status",
                        "failure_reason",
                        "updated_at",
                    ]
                )
    return HttpResponse(status=200)


def order_confirmation(request, reference):
    order = get_object_or_404(Order.objects.prefetch_related("items"), reference=reference)
    if order.customer_id and order.customer_id != request.user.pk:
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    return render(
        request,
        "core/order_confirmation.html",
        {"order": order, "store_settings": StoreSettings.load()},
    )


def _customer_can_cancel_order(order):
    if order.status not in {Order.Status.PENDING, Order.Status.CONFIRMED}:
        return False
    if (
        order.payment_received
        or order.payment_status
        in {Order.PaymentStatus.PENDING, Order.PaymentStatus.CAPTURED}
    ):
        return False
    return all(
        seller_order.status
        in {SellerOrder.Status.PENDING, SellerOrder.Status.CONFIRMED}
        and not seller_order.delhivery_waybill
        for seller_order in order.seller_orders.all()
    )


@login_required(login_url="login")
@require_POST
def cancel_order(request, order_id):
    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update()
            .filter(customer=request.user)
            .prefetch_related("seller_orders"),
            pk=order_id,
        )
        if not _customer_can_cancel_order(order):
            messages.error(
                request,
                "This order can no longer be cancelled here. Contact support for help, especially if payment was made.",
            )
            return redirect("my_orders")

        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])
        release_order_stock(order.pk)
        notify_order_updated(order.pk, ["status"])
        notify_order_cancelled(order.pk)

    messages.success(
        request,
        f"Order #{order.pk} has been cancelled. Any refund for a completed online payment must be arranged with support.",
    )
    return redirect("my_orders")


@login_required(login_url="login")
def my_orders(request):
    orders = Order.objects.filter(customer=request.user).prefetch_related(
        "items",
        "seller_orders",
    )
    for order in orders:
        order.can_customer_cancel = _customer_can_cancel_order(order)
        order.cancellation_needs_support = (
            order.status in {Order.Status.PENDING, Order.Status.CONFIRMED}
            and not order.can_customer_cancel
        )
    base_orders = Order.objects.filter(customer=request.user)
    store_settings = StoreSettings.load()
    return render(
        request,
        "core/my_orders.html",
        {
            "orders": orders,
            "support_email": store_settings.support_email,
            "support_phone": store_settings.support_phone,
            "order_count": base_orders.count(),
            "open_order_count": base_orders.filter(
                status__in=[
                    Order.Status.PENDING,
                    Order.Status.CONFIRMED,
                    Order.Status.PROCESSING,
                    Order.Status.SHIPPED,
                ]
            ).count(),
            "completed_order_count": base_orders.filter(
                status=Order.Status.COMPLETED
            ).count(),
        },
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = CustomerSignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("home")

    return render(request, "core/register.html", {"form": form})


def seller_register(request):
    if request.user.is_authenticated and SellerProfile.objects.filter(user=request.user).exists():
        return redirect("seller_dashboard")

    if request.user.is_authenticated:
        form = SellerProfileForm(
            request.POST or None,
            request.FILES or None,
            initial={
                "email": request.user.email,
                "contact_name": request.user.get_full_name() or request.user.username,
            },
        )
        if request.method == "POST" and form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.email = profile.email or request.user.email
            profile.status = SellerProfile.Status.PENDING
            profile.save()
            messages.success(
                request,
                "Your seller application was submitted. Products become public after admin approval.",
            )
            return redirect("seller_dashboard")
        template = "core/seller/register.html"
    else:
        form = SellerRegistrationForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            with transaction.atomic():
                user = form.save()
            login(request, user)
            messages.success(
                request,
                "Your seller application was submitted. Products become public after admin approval.",
            )
            return redirect("seller_dashboard")
        template = "core/seller/register.html"

    return render(
        request,
        template,
        {
            "form": form,
            "existing_account": request.user.is_authenticated,
        },
    )


@seller_account_required
def seller_dashboard(request):
    profile = request.user.seller_profile
    products = Product.objects.filter(seller=profile).select_related("category")
    seller_orders = (
        SellerOrder.objects.filter(seller=profile)
        .select_related("order")
        .prefetch_related("items")
    )
    quote_requests = QuoteRequest.objects.filter(
        product__seller=profile,
    ).select_related("product", "customer")
    return render(
        request,
        "core/seller/dashboard.html",
        {
            "seller": profile,
            "products": products[:8],
            "product_count": products.count(),
            "active_product_count": products.filter(is_active=True).count(),
            "order_count": seller_orders.count(),
            "open_quote_count": quote_requests.exclude(
                status__in=[QuoteRequest.Status.ACCEPTED, QuoteRequest.Status.CLOSED]
            ).count(),
            "recent_orders": seller_orders[:5],
            "recent_quotes": quote_requests[:5],
        },
    )


@seller_account_required
def seller_profile_edit(request):
    profile = request.user.seller_profile
    form = SellerProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=profile,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your seller profile has been updated.")
        return redirect("seller_dashboard")
    return render(
        request,
        "core/seller/profile_form.html",
        {"seller": profile, "form": form},
    )


def seller_public_profile(request, slug):
    seller = get_object_or_404(
        SellerProfile.objects.select_related("user"),
        slug=slug,
        status=SellerProfile.Status.APPROVED,
        user__is_active=True,
    )
    products = public_products().filter(seller=seller)
    categories = Category.objects.filter(is_active=True)
    return render(
        request,
        "core/seller/public_profile.html",
        {
            "seller": seller,
            "products": products,
            "categories": categories,
            "wishlist_ids": request.session.get("wishlist", []),
        },
    )


@seller_account_required
def seller_product_list(request):
    profile = request.user.seller_profile
    products = (
        Product.objects.filter(seller=profile)
        .select_related("category")
        .prefetch_related("price_tiers")
    )
    return render(
        request,
        "core/seller/product_list.html",
        {"seller": profile, "products": products},
    )


@seller_account_required
def seller_product_create(request):
    profile = request.user.seller_profile
    form = SellerProductForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        product = form.save(commit=False)
        product.seller = profile
        product.supplier = None
        product.is_featured = False
        if not profile.is_approved:
            product.is_active = False
        form.save()
        messages.success(request, "Product saved to your seller catalog.")
        return redirect("seller_products")
    return render(
        request,
        "core/seller/product_form.html",
        {"seller": profile, "form": form, "page_title": "Add a product"},
    )


@seller_account_required
def seller_product_edit(request, product_id):
    profile = request.user.seller_profile
    product = get_object_or_404(Product, pk=product_id, seller=profile)
    form = SellerProductForm(
        request.POST or None,
        request.FILES or None,
        instance=product,
    )
    if request.method == "POST" and form.is_valid():
        product = form.save(commit=False)
        product.seller = profile
        product.supplier = None
        product.is_featured = False
        if not profile.is_approved:
            product.is_active = False
        form.save()
        messages.success(request, "Product changes saved.")
        return redirect("seller_products")
    return render(
        request,
        "core/seller/product_form.html",
        {
            "seller": profile,
            "form": form,
            "product": product,
            "page_title": "Edit product",
        },
    )


def _seller_order_status_choices(order):
    next_status = {
        SellerOrder.Status.PENDING: SellerOrder.Status.CONFIRMED,
        SellerOrder.Status.CONFIRMED: SellerOrder.Status.PROCESSING,
    }.get(order.status)
    choices = [(order.status, order.get_status_display())]
    if next_status:
        choices.append((next_status, SellerOrder.Status(next_status).label))
    return choices


@seller_account_required
def seller_orders(request):
    profile = request.user.seller_profile
    if not profile.is_approved:
        messages.warning(request, "Seller order management is available after account approval.")
        return redirect("seller_dashboard")
    orders = (
        SellerOrder.objects.filter(seller=profile)
        .select_related("order")
        .prefetch_related("items__product")
    )
    for seller_order in orders:
        item_products = [
            item.product
            for item in seller_order.items.all()
            if item.product_id
        ]
        initial = {}
        if item_products and all(
            product.shipping_weight_grams
            and product.shipping_length_cm
            and product.shipping_width_cm
            and product.shipping_height_cm
            for product in item_products
        ):
            initial = {
                "package_weight_grams": sum(
                    item.product.shipping_weight_grams * item.quantity
                    for item in seller_order.items.all()
                ),
                "package_length_cm": max(
                    product.shipping_length_cm for product in item_products
                ),
                "package_width_cm": max(
                    product.shipping_width_cm for product in item_products
                ),
                "package_height_cm": sum(
                    item.product.shipping_height_cm * item.quantity
                    for item in seller_order.items.all()
                ),
            }
        seller_order.shipment_form = DelhiveryShipmentForm(
            initial=initial or None
        )
    return render(
        request,
        "core/seller/orders.html",
        {
            "seller": profile,
            "orders": orders,
            "delhivery_configured": delhivery_is_configured(),
        },
    )


@seller_account_required
@require_POST
def seller_order_update(request, order_id):
    profile = request.user.seller_profile
    if not profile.is_approved:
        messages.error(request, "Your seller account must be approved to update orders.")
        return redirect("seller_dashboard")
    seller_order = get_object_or_404(
        SellerOrder.objects.filter(
            seller=profile,
            order__status__in=[Order.Status.PENDING, Order.Status.CONFIRMED],
        ).select_related("order"),
        pk=order_id,
    )
    form = SellerOrderStatusForm(
        request.POST,
        instance=seller_order,
        status_choices=_seller_order_status_choices(seller_order),
    )
    if form.is_valid():
        form.save()
        notify_seller_order_updated(seller_order.pk)
        messages.success(request, f"Order #{seller_order.order.pk} was updated.")
    else:
        messages.error(request, "That order update is not allowed. Follow the order status steps.")
    return redirect("seller_orders")


@seller_account_required
@require_POST
def seller_shipment_create(request, order_id):
    profile = request.user.seller_profile
    if not profile.is_approved:
        messages.error(request, "Your seller account must be approved to create a shipment.")
        return redirect("seller_dashboard")
    seller_order = get_object_or_404(
        SellerOrder.objects.filter(
            seller=profile,
            status=SellerOrder.Status.PROCESSING,
            order__status__in=[Order.Status.PENDING, Order.Status.CONFIRMED, Order.Status.PROCESSING],
        )
        .select_related("order"),
        pk=order_id,
    )
    if seller_order.delhivery_waybill:
        messages.error(request, "This order already has a Delhivery waybill.")
        return redirect("seller_orders")
    form = DelhiveryShipmentForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter valid packed parcel weight and dimensions.")
        return redirect("seller_orders")
    try:
        shipment = create_shipment(seller_order, form.cleaned_data)
    except DelhiveryError as exc:
        messages.error(request, str(exc))
        return redirect("seller_orders")

    now = timezone.now()
    seller_order.delhivery_waybill = shipment["waybill"]
    seller_order.delhivery_shipment_id = shipment["shipment_id"]
    seller_order.delhivery_status = shipment["status"]
    seller_order.package_weight_grams = form.cleaned_data["package_weight_grams"]
    seller_order.package_length_cm = form.cleaned_data["package_length_cm"]
    seller_order.package_width_cm = form.cleaned_data["package_width_cm"]
    seller_order.package_height_cm = form.cleaned_data["package_height_cm"]
    seller_order.shipped_at = now
    seller_order.status = SellerOrder.Status.SHIPPED
    seller_order.save(
        update_fields=[
            "delhivery_waybill",
            "delhivery_shipment_id",
            "delhivery_status",
            "package_weight_grams",
            "package_length_cm",
            "package_width_cm",
            "package_height_cm",
            "shipped_at",
            "status",
            "updated_at",
        ]
    )
    seller_order.shipping_events.create(
        status=shipment["status"],
        description="Shipment created through Delhivery.",
        occurred_at=now,
    )
    messages.success(request, f"Delhivery shipment created. Waybill: {shipment['waybill']}.")
    return redirect("seller_orders")


@seller_account_required
@require_POST
def seller_shipment_refresh(request, order_id):
    profile = request.user.seller_profile
    if not profile.is_approved:
        messages.error(request, "Your seller account must be approved to refresh shipment tracking.")
        return redirect("seller_dashboard")
    seller_order = get_object_or_404(
        SellerOrder.objects.filter(seller=profile).select_related("order"),
        pk=order_id,
    )
    if not seller_order.delhivery_waybill:
        messages.error(request, "This order does not have a Delhivery waybill yet.")
        return redirect("seller_orders")
    try:
        snapshot = fetch_tracking(seller_order.delhivery_waybill)
    except DelhiveryError as exc:
        messages.error(request, str(exc))
        return redirect("seller_orders")

    for scan in snapshot.scans:
        seller_order.shipping_events.get_or_create(
            status=scan["status"],
            description=scan["description"],
            occurred_at=scan["occurred_at"],
        )
    seller_order.delhivery_status = snapshot.status
    update_fields = ["delhivery_status", "updated_at"]
    status_normalized = snapshot.status.casefold().replace("_", " ")
    if status_normalized == "delivered" or status_normalized.endswith(" delivered"):
        delivered_at = snapshot.status_time or timezone.now()
        if timezone.is_naive(delivered_at):
            delivered_at = timezone.make_aware(delivered_at)
        seller_order.delivered_at = seller_order.delivered_at or delivered_at
        seller_order.status = SellerOrder.Status.COMPLETED
        update_fields.extend(["delivered_at", "status"])
        payout = SellerPayout.objects.filter(seller_order=seller_order).first()
        if payout:
            available_at = seller_order.delivered_at + timedelta(
                days=settings.SUPPLYHUB_PAYOUT_HOLD_DAYS
            )
            payout.available_at = available_at
            payout.status = (
                SellerPayout.Status.READY
                if available_at <= timezone.now()
                else SellerPayout.Status.HOLD
            )
            payout.save(update_fields=["available_at", "status", "updated_at"])
    seller_order.save(update_fields=update_fields)
    seller_order.shipping_events.get_or_create(
        status=snapshot.status,
        description="Current status refreshed from Delhivery.",
        occurred_at=snapshot.status_time,
    )
    messages.success(request, f"Tracking updated: {snapshot.status}.")
    return redirect("seller_orders")


@seller_account_required
def seller_quotes(request):
    profile = request.user.seller_profile
    if not profile.is_approved:
        messages.warning(request, "Quote response tools are available after account approval.")
        return redirect("seller_dashboard")
    quotes = QuoteRequest.objects.filter(
        Q(seller=profile) | Q(product__seller=profile),
    ).select_related("product", "customer", "seller").distinct()
    if request.method == "POST":
        quote = get_object_or_404(
            quotes,
            pk=request.POST.get("quote_id"),
        )
        form = SellerQuoteResponseForm(request.POST, instance=quote)
        if form.is_valid():
            quote = form.save(commit=False)
            if quote.seller_id is None and quote.product_id:
                quote.seller = quote.product.seller
            quote.seller_responded_at = timezone.now()
            if quote.status == QuoteRequest.Status.PENDING:
                quote.status = QuoteRequest.Status.QUOTED
            quote.save(
                update_fields=[
                    "seller_quoted_unit_price",
                    "seller_response",
                    "seller_responded_at",
                    "status",
                    "updated_at",
                    "seller",
                ]
            )
            notify_quote_updated(
                quote.pk,
                ["seller_quoted_unit_price", "seller_response", "status"],
            )
            messages.success(request, "Your reply has been saved for the buyer.")
            return redirect("seller_quotes")
        return render(
            request,
            "core/seller/quotes.html",
            {"seller": profile, "quotes": quotes, "response_form": form, "form_quote_id": quote.pk},
        )
    return render(
        request,
        "core/seller/quotes.html",
        {"seller": profile, "quotes": quotes, "response_form": SellerQuoteResponseForm()},
    )

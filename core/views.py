from decimal import Decimal

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CustomerSignUpForm, OrderCheckoutForm, QuoteRequestForm
from .models import Category, Order, OrderItem, Product, QuoteRequest, StoreSettings
from .notifications import notify_order_created, notify_quote_created


def _cart_rows(request):
    cart = request.session.get("cart", {})
    products = Product.objects.filter(
        pk__in=cart,
        is_active=True,
        category__is_active=True,
    ).select_related("category")
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
        product_count=Count("products", filter=Q(products__is_active=True))
    )
    products = Product.objects.filter(
        is_active=True,
        category__is_active=True,
    ).select_related("category")
    wishlist_ids = request.session.get("wishlist", [])

    return render(
        request,
        "core/home.html",
        {
            "categories": categories,
            "product_categories": categories.filter(product_count__gt=0),
            "products": products,
            "cart_count": sum(request.session.get("cart", {}).values()),
            "wishlist_ids": wishlist_ids,
            "store_settings": store_settings,
        },
    )


def quote_request(request):
    initial = {}
    product_id = request.GET.get("product")
    if product_id:
        initial["product"] = product_id
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
        Product,
        pk=request.POST.get("product_id"),
        is_active=True,
        category__is_active=True,
    )
    cart = request.session.get("cart", {})
    product_key = str(product.pk)
    cart[product_key] = int(cart.get(product_key, 0)) + product.minimum_order_quantity
    request.session["cart"] = cart
    count = sum(cart.values())
    return JsonResponse({"ok": True, "cart_count": count, "message": f"{product.name} added to cart"})


@require_POST
def buy_now(request, product_id):
    product = get_object_or_404(
        Product,
        pk=product_id,
        is_active=True,
        category__is_active=True,
    )
    request.session["cart"] = {str(product.pk): product.minimum_order_quantity}
    return redirect("checkout")


@require_POST
def buy_sample(request, product_id):
    product = get_object_or_404(
        Product,
        pk=product_id,
        is_active=True,
        category__is_active=True,
    )
    if product.sample_price is None:
        messages.error(request, "A sample is not available for this product.")
        return redirect("home")
    request.session["cart"] = {str(product.pk): product.sample_quantity}
    return redirect("checkout")


@require_POST
def toggle_wishlist(request):
    product = get_object_or_404(
        Product,
        pk=request.POST.get("product_id"),
        is_active=True,
        category__is_active=True,
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
    products = Product.objects.filter(
        pk__in=wishlist_ids,
        is_active=True,
        category__is_active=True,
    ).select_related("category")
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
    product = get_object_or_404(Product, pk=product_id)
    cart = request.session.get("cart", {})
    product_key = str(product.pk)
    action = request.POST.get("action")

    if action == "remove":
        cart.pop(product_key, None)
        messages.success(request, f"{product.name} removed from your cart.")
    elif action == "update":
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
    form = OrderCheckoutForm(
        request.POST or None,
        payment_choices=payment_choices,
    )
    if request.method == "POST" and form.is_valid():
        cart = request.session.get("cart", {})
        with transaction.atomic():
            product_ids = [int(product_id) for product_id in cart]
            locked_products = Product.objects.select_for_update().filter(
                pk__in=product_ids,
                is_active=True,
                category__is_active=True,
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

            order = form.save(commit=False)
            order.shipping_charge = shipping_charge
            if request.user.is_authenticated:
                order.customer = request.user
            order.save()
            total = Decimal("0.00")
            for product_id, raw_quantity in cart.items():
                product = products[int(product_id)]
                quantity = int(raw_quantity)
                unit_price = product.unit_price_for_quantity(quantity)
                is_sample = (
                    product.sample_price is not None
                    and quantity == product.sample_quantity
                )
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    unit=product.unit,
                    unit_price=unit_price,
                    quantity=quantity,
                    is_sample=is_sample,
                )
                total += unit_price * quantity
            order.total_amount = total + order.shipping_charge
            order.save(update_fields=["total_amount"])
            notify_order_created(order.pk)

        request.session["cart"] = {}
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
        },
    )


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


@login_required(login_url="login")
def my_orders(request):
    orders = Order.objects.filter(customer=request.user).prefetch_related("items")
    return render(request, "core/my_orders.html", {"orders": orders})


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = CustomerSignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("home")

    return render(request, "core/register.html", {"form": form})

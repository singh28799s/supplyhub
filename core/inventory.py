from django.db import transaction
from django.db.models import F

from .models import Order, OrderItem, Product


def reserve_stock(product: Product, quantity: int) -> None:
    if not product.track_inventory:
        return
    if product.stock_quantity < quantity:
        raise ValueError(
            f"{product.name} has only {product.stock_quantity} units available."
        )
    product.stock_quantity -= quantity
    product.save(update_fields=["stock_quantity"])


@transaction.atomic
def release_order_stock(order_id: int) -> None:
    order = Order.objects.select_for_update().get(pk=order_id)
    items = list(
        OrderItem.objects.select_for_update()
        .filter(order=order, stock_reserved=True)
        .select_related("product")
    )
    for item in items:
        if item.product_id:
            Product.objects.filter(pk=item.product_id).update(
                stock_quantity=F("stock_quantity") + item.quantity
            )
        item.stock_reserved = False
        item.save(update_fields=["stock_reserved"])

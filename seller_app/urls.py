from django.urls import path

from core import views

urlpatterns = [
    path("sellers/register/", views.seller_register, name="seller_register"),
    path("seller/security/verify/", views.seller_mfa, name="seller_mfa"),
    path(
        "seller/security/email/verify/<str:token>/",
        views.seller_email_verify,
        name="seller_email_verify",
    ),
    path("seller/dashboard/", views.seller_dashboard, name="seller_dashboard"),
    path("seller/profile/", views.seller_profile_edit, name="seller_profile_edit"),
    path("seller/products/", views.seller_product_list, name="seller_products"),
    path("seller/products/add/", views.seller_product_create, name="seller_product_create"),
    path(
        "seller/products/<int:product_id>/edit/",
        views.seller_product_edit,
        name="seller_product_edit",
    ),
    path("seller/orders/", views.seller_orders, name="seller_orders"),
    path(
        "seller/orders/<int:order_id>/update/",
        views.seller_order_update,
        name="seller_order_update",
    ),
    path(
        "seller/orders/<int:order_id>/ship/",
        views.seller_shipment_create,
        name="seller_shipment_create",
    ),
    path(
        "seller/orders/<int:order_id>/tracking/refresh/",
        views.seller_shipment_refresh,
        name="seller_shipment_refresh",
    ),
    path("seller/quotes/", views.seller_quotes, name="seller_quotes"),
]

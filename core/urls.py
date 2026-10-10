from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import CustomerAuthenticationForm

urlpatterns = [
    path("", views.home, name="home"),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),
    path("cart/", views.cart_detail, name="cart"),
    path("cart/add/", views.add_to_cart, name="add_to_cart"),
    path("buy-now/<int:product_id>/", views.buy_now, name="buy_now"),
    path("buy-sample/<int:product_id>/", views.buy_sample, name="buy_sample"),
    path("cart/update/<int:product_id>/", views.update_cart, name="update_cart"),
    path("wishlist/", views.wishlist_detail, name="wishlist"),
    path("wishlist/toggle/", views.toggle_wishlist, name="toggle_wishlist"),
    path("checkout/", views.checkout, name="checkout"),
    path("payments/razorpay/verify/", views.razorpay_verify, name="razorpay_verify"),
    path("payments/razorpay/webhook/", views.razorpay_webhook, name="razorpay_webhook"),
    path("orders/", views.my_orders, name="my_orders"),
    path("orders/<int:order_id>/cancel/", views.cancel_order, name="cancel_order"),
    path("orders/confirmation/<uuid:reference>/", views.order_confirmation, name="order_confirmation"),
    path("quotes/request/", views.quote_request, name="quote_request"),
    path("quotes/confirmation/<uuid:reference>/", views.quote_confirmation, name="quote_confirmation"),
    path("quotes/my/", views.my_quotes, name="my_quotes"),
    path("sellers/register/", views.seller_register, name="seller_register"),
    path("sellers/<slug:slug>/", views.seller_public_profile, name="seller_public_profile"),
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
    path("register/", views.register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="core/login.html",
            authentication_form=CustomerAuthenticationForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="home"), name="logout"),
]

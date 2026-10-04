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
    path("orders/", views.my_orders, name="my_orders"),
    path("orders/confirmation/<uuid:reference>/", views.order_confirmation, name="order_confirmation"),
    path("quotes/request/", views.quote_request, name="quote_request"),
    path("quotes/confirmation/<uuid:reference>/", views.quote_confirmation, name="quote_confirmation"),
    path("quotes/my/", views.my_quotes, name="my_quotes"),
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

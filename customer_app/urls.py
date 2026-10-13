from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from core import views
from core.forms import CustomerAuthenticationForm

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
    path(
        "orders/confirmation/<uuid:reference>/",
        views.order_confirmation,
        name="order_confirmation",
    ),
    path("quotes/request/", views.quote_request, name="quote_request"),
    path(
        "quotes/confirmation/<uuid:reference>/",
        views.quote_confirmation,
        name="quote_confirmation",
    ),
    path("quotes/my/", views.my_quotes, name="my_quotes"),
    path("sellers/<slug:slug>/", views.seller_public_profile, name="seller_public_profile"),
    path("register/", views.register, name="register"),
    path(
        "login/",
        views.SupplyHubLoginView.as_view(
            template_name="core/login.html",
            authentication_form=CustomerAuthenticationForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="core/password_reset_form.html",
            email_template_name="core/password_reset_email.html",
            subject_template_name="core/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="core/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="core/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="core/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="home"), name="logout"),
]

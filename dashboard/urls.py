from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path(
        "sellers/<int:seller_id>/status/",
        views.seller_status_update,
        name="seller_status_update",
    ),
]

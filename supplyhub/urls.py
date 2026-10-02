"""URL configuration for SupplyHub."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("staff-dashboard/", include("dashboard.urls")),
    path("", include("core.urls")),
]

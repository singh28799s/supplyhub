from customer_app.urls import urlpatterns as customer_urlpatterns
from seller_app.urls import urlpatterns as seller_urlpatterns

urlpatterns = [*customer_urlpatterns, *seller_urlpatterns]

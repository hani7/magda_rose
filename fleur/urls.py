# fleur/urls.py
from django.urls import path

from fleur import api
from . import views
from django.contrib.auth import views as auth_views
from . import views as shop

app_name = "fleur"

urlpatterns = [
    path("home/", shop.home, name="client_landing"),                 # video home (NEW)
    path("shop/", shop.product_list, name="client_home"), 
    path("shop/", shop.product_list, name="product_list"),      # alias pour compatibilité
    path("shop/c/<slug:category_slug>/", shop.product_list, name="product_list_by_category"),
    # No product_detail route anymore
    path("mes-bouquets/", shop.mes_bouquets, name="mes_bouquets"),

    path("p/<slug:slug>/buy/", views.buy_now, name="buy_now"),
    path("payment/<int:pk>/insert/", views.payment_insert, name="payment_insert"),
    path("payment/<int:pk>/success/", views.payment_success, name="payment_success"),
    path("payment/<int:pk>/failed/", views.payment_failed, name="payment_failed"),


    path("backoffice/login/", auth_views.LoginView.as_view(template_name="backoffice/login.html"), name="bo_login"),
    path("backoffice/logout/", auth_views.LogoutView.as_view(next_page="fleur:bo_login"), name="bo_logout"),

    # Back-office dashboard & CRUD
    path("backoffice/", views.dashboard, name="bo_dashboard"),

    path("backoffice/products/", views.product_list, name="bo_product_list"),
    path("backoffice/products/new/", views.product_create, name="bo_product_create"),

    path("backoffice/categories/", views.category_list, name="bo_category_list"),
    path("backoffice/categories/new/", views.category_create, name="bo_category_create"),
    path("backoffice/home-video/", shop.home_video_edit, name="bo_home_video"),
    path("backoffice/orders/", views.order_list, name="bo_order_list"),

    path("api/payment/insert-event/", api.payment_insert_event, name="api_payment_insert_event"),

    path("backoffice/slots/", shop.backoffice_slots_list, name="bo_slots_list"),
    path("backoffice/slots/new/", shop.backoffice_slot_create, name="bo_slot_create"),
    path("backoffice/slots/<int:pk>/edit/", shop.backoffice_slot_edit, name="bo_slot_edit"),
    path("backoffice/slots/seed12/", shop.backoffice_slots_seed12, name="bo_slots_seed12")

]

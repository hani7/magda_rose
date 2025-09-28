# magda_app/urls.py
from django.urls import path
from . import views

app_name = "magda"

urlpatterns = [
    # Public product pages
    path("p/<int:pk>/", views.product_detail, name="product_detail_pk"),
    path("p/s/<slug:slug>/", views.product_detail, name="product_detail_slug"),
    path("p/<int:pk>/buy/", views.create_order, name="create_order"),

    # Staff
    path("manage/", views.dashboard, name="dashboard"),
    path("manage/products/", views.admin_product_list, name="admin_product_list"),
    path("manage/products/new/", views.product_create, name="product_create"),

    # Auth
    path("login/", auth_views.LoginView.as_view(template_name="magda_app/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="magda:login"), name="logout"),
]

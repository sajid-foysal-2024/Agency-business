from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("demo/<str:reference>/", views.DemoCheckoutView.as_view(), name="demo"),
    path("webhook/demo/", views.demo_webhook, name="demo_webhook"),
    path("sslcommerz/ipn/", views.sslcommerz_ipn, name="sslcommerz_ipn"),
    path("sslcommerz/return/<str:outcome>/", views.sslcommerz_return, name="sslcommerz_return"),
    path("<str:reference>/instructions/", views.payment_instructions, name="instructions"),
]

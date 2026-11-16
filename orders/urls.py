from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/<int:package_id>/", views.CheckoutView.as_view(), name="checkout"),
    path("quote/", views.QuoteRequestView.as_view(), name="quote"),
    path("account/", views.dashboard, name="dashboard"),
    path("orders/<str:number>/", views.order_detail, name="detail"),
    path("orders/<str:number>/review/", views.OrderReviewView.as_view(), name="review"),
    path("orders/<str:number>/cancel/", views.order_cancel, name="cancel"),
    path("orders/<str:number>/coupon/", views.order_coupon, name="coupon"),
    path("orders/<str:number>/invoice/", views.invoice_view, name="invoice"),
]

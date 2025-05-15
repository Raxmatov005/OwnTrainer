# click_app/urls.py
from django.urls import path
from .views import (
    CreateClickOrderView,
    ClickPrepareAPIView,
    ClickCompleteAPIView,
    OrderTestView,
    HealthCheckAPIView,
    PaymentSuccessView
)

urlpatterns = [
    path('payment/click/prepare/', ClickPrepareAPIView.as_view(), name='click_prepare'),
    path('payment/click/complete/', ClickCompleteAPIView.as_view(), name='click_complete'),
    path('click/order/', CreateClickOrderView.as_view(), name='create_click_order'),
    path('click/transaction/', OrderTestView.as_view(), name='click_transaction'),
    path('health/', HealthCheckAPIView.as_view(), name='health_check'),
    path('payment-success/', PaymentSuccessView.as_view(), name='payment_success'),
]
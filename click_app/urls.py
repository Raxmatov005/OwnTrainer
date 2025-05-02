from django.urls import path
from . import views

urlpatterns = [
    path('', views.CreateClickOrderView.as_view()),
    path('click/transaction/', views.OrderTestView.as_view()),
    path('payment/click/prepare/', views.ClickPrepareAPIView.as_view(), name='click-prepare'),
    path('payment/click/complete/', views.ClickCompleteAPIView.as_view(), name='click-complete'),
]

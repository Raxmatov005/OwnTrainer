from django.urls import path
from . import views

urlpatterns = [
    path('', views.CreateClickOrderView.as_view()),
    path('click/transaction/', views.OrderTestView.as_view()),
]

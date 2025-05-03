# from django.urls import path
# from . import views
#
# urlpatterns = [
#     path('', views.CreateClickOrderView.as_view()),
#     path('click/order/', CreateClickOrderView.as_view(), name='create_click_order'),
#     path('click/transaction/', views.OrderTestView.as_view()),
#     path('payment/click/prepare/', views.ClickPrepareAPIView.as_view(), name='click-prepare'),
#     path('payment/click/complete/', views.ClickCompleteAPIView.as_view(), name='click-complete'),
# ]


from django.urls import path
from click_app.views import CreateClickOrderView, ClickPrepareAPIView, ClickCompleteAPIView

urlpatterns = [
    path('click/prepare/', ClickPrepareAPIView.as_view(), name='click_prepare'),
    path('click/complete/', ClickCompleteAPIView.as_view(), name='click_complete'),
    path('click/order/', CreateClickOrderView.as_view(), name='create_click_order'),
]
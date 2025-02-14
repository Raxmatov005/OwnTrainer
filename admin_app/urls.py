from food.urls import urlpatterns
from django.urls import path,include

from  admin_app.views import  AdminUserStatisticsView,AdminGetAllUsersView, AdminLoginView



urlpatterns=[
    path("admin/dashboard",AdminUserStatisticsView.as_view(),name="admindashboard"),
    path('admin/users/', AdminGetAllUsersView.as_view(), name='admin_get_all_users'),
    path('admin/login',AdminLoginView.as_view(), name='admin_login'),
]
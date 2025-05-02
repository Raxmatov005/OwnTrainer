from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.views import TokenObtainPairView
from payment.views import PaymeCallBackAPIView, UnifiedPaymentInitView
from django.contrib import admin
from users_app.views import CustomTokenRefreshView
from click_app.views import HealthCheckAPIView

schema_view = get_schema_view(
    openapi.Info(
        title="My API",
        default_version='v1',
        description="Test description",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@myapi.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    url="https://owntrainer.uz",
)





urlpatterns = [
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('api/users/', include('users_app.urls')),
    path("api/exercise/", include('exercise.urls')),
    path("api/food/", include('food.urls')),
    path("api/admin/", include('admin_app.urls')),
    path('admin/', admin.site.urls),
    path("payment/update/", PaymeCallBackAPIView.as_view()),
    path('init/', UnifiedPaymentInitView.as_view(), name='payment-init'),
    path('', include('click_app.urls')),
    path('health/', HealthCheckAPIView.as_view(), name='health-check'),
]


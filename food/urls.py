from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static
from food.views import (
    MealViewSet,
    MealCompletionViewSet,
    CompleteMealView,
    MealStepViewSet,
    UserDailyMealsView,
    MealDetailView
)

meal_router = DefaultRouter()
meal_router.register(r'', MealViewSet, basename='meal')

meal_completion_router = DefaultRouter()
meal_completion_router.register(r'', MealCompletionViewSet, basename='mealcompletion')

meal_step_router = DefaultRouter()
meal_step_router.register(r'', MealStepViewSet, basename='mealstep')

urlpatterns = [
    path('api/meals/', include((meal_router.urls, 'meal'))),
    path('api/meal-steps/', include((meal_step_router.urls, 'mealsteps'))),
    path('api/mealcompletion/', include((meal_completion_router.urls, 'mealcompletion'))),
    path('api/meal/complete/', CompleteMealView.as_view(), name='complete-meal'),
    path('meals/daily/', UserDailyMealsView.as_view(), name='user-daily-meals'),
    path('api/meals/<int:meal_id>/details/', MealDetailView.as_view(), name='meal_detail'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from exercise.views import (ProgramViewSet, SessionViewSet,
                            ExerciseViewSet, WorkoutCategoryViewSet,
                            UserProgramViewSet, ProgressView,
                            StartSessionView)

from exercise.views import ExerciseStartView
from django.conf import settings
from django.conf.urls.static import static


router = DefaultRouter()
router.register(r'programs', ProgramViewSet, basename='program')
router.register(r'sessions', SessionViewSet, basename='session')
router.register(r'exercises', ExerciseViewSet, basename='exercise')
router.register(r'workout-categories', WorkoutCategoryViewSet, basename='workoutcategory')
router.register(r'userprogram', UserProgramViewSet, basename='userprogram')

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/sessions/complete/', StartSessionView.as_view(), name='start_session'),
    path('api/user/statistics/', ProgressView.as_view(), name='user-progress'),
    path('api/start-exercise/', ExerciseStartView.as_view(), name='start-exercise'),
]


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from exercise.views import (ProgramViewSet, SessionViewSet,
                            ExerciseViewSet, WorkoutCategoryViewSet,
                            UserProgramViewSet, ProgressView,
                            StartSessionView)

from exercise.views import ExerciseStartView


router = DefaultRouter()
router.register(r'programs', ProgramViewSet, basename='program')
router.register(r'sessions', SessionViewSet, basename='session')
router.register(r'exercises', ExerciseViewSet, basename='exercise')
router.register(r'workout-categories', WorkoutCategoryViewSet, basename='workoutcategory')
router.register(r'userprogram', UserProgramViewSet, basename='userprogram')


urlpatterns = [
    path('api/', include(router.urls)),
]

urlpatterns += [
    path('sessions/complete/', StartSessionView.as_view(), name='start_session'),
    path('user/statistics/',ProgressView.as_view(),name='user-progress'),
]

urlpatterns += [
    path('api/start-exercise/', ExerciseStartView.as_view(), name='start-exercise'),

]

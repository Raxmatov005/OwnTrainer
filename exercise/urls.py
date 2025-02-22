from django.urls import path, include
from rest_framework.routers import DefaultRouter
from exercise.views import (ProgramViewSet, SessionViewSet,
                            ExerciseViewSet,UserProgramViewSet,
                            ProgressView,CompleteBlockView)

from django.conf import settings
from django.conf.urls.static import static


router = DefaultRouter()
router.register(r'programs', ProgramViewSet, basename='program')
router.register(r'sessions', SessionViewSet, basename='session')
router.register(r'exercises', ExerciseViewSet, basename='exercise')
router.register(r'userprogram', UserProgramViewSet, basename='userprogram')

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/sessions/complete-block/', CompleteBlockView.as_view(), name='complete-block'),
    path('api/user/statistics/', ProgressView.as_view(), name='user-progress'),
]


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

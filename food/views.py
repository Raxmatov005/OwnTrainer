from datetime import timedelta
from django.utils import timezone
from django.utils.timezone import localdate, now
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils.translation import gettext_lazy as _
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
import json

from users_app.models import Meal, MealSteps, MealCompletion, SessionCompletion, Session, UserProgram, UserSubscription
from food.serializers import *

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.decorators import action
from drf_yasg.utils import swagger_auto_schema
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from exercise.views import maybe_mark_session_completed
# Import your serializerskkkkkkkk


translator = Translator()


def translate_text(text, target_language):
    try:
        translation = translator.translate(text, dest=target_language)
        return translation.text if translation else text
    except Exception as e:
        print(f"Translation error: {e}")
        return text



# food/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema

from users_app.models import Meal, UserProgram, UserSubscription
from .serializers import (
    MealListSerializer,
    MealDetailSerializer,
    MealCreateSerializer,
    MealUpdateSerializer,
    MealImageUploadSerializer
)

class MealViewSet(viewsets.ModelViewSet):
    """
    JSON-only create/update for Meal, plus a separate endpoint for 'food_photo'.
    """
    queryset = Meal.objects.all()
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]  # main endpoints: JSON only

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Meal.objects.none()

        user = self.request.user
        # Allow both staff and superusers to bypass subscription checks
        if user.is_staff or user.is_superuser:
            return Meal.objects.all().prefetch_related("steps")

        user_program = UserProgram.objects.filter(user=user, is_active=True).first()
        if not user_program:
            return Meal.objects.none()

        has_active_subscription = UserSubscription.objects.filter(
            user=user,
            is_active=True,
            end_date__gte=timezone.now().date()
        ).exists()

        if not has_active_subscription:
            return Meal.objects.none()

        return Meal.objects.filter(
            sessions__program=user_program.program,
            goal_type=user.goal
        ).distinct().prefetch_related("steps")

    def get_serializer_class(self):
        if self.action == 'list':
            return MealListSerializer
        elif self.action == 'retrieve':
            return MealDetailSerializer
        elif self.action == 'create':
            return MealCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return MealUpdateSerializer
        return MealListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            context['language'] = getattr(self.request.user, 'language', 'en')
        else:
            context['language'] = self.request.query_params.get('lang', 'en')
        return context

    @swagger_auto_schema(request_body=MealCreateSerializer)
    def create(self, request, *args, **kwargs):
        """
        Staff-only creation of a Meal with optional nested MealSteps.
        """
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(request_body=MealUpdateSerializer)
    def update(self, request, pk=None, *args, **kwargs):
        """
        Staff-only full update of a Meal (PUT).
        Replaces nested MealSteps if provided.
        """
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, pk, *args, **kwargs)

    @swagger_auto_schema(request_body=MealUpdateSerializer)
    def partial_update(self, request, pk=None, *args, **kwargs):
        """
        Staff-only partial update of a Meal (PATCH).
        Updates nested MealSteps if provided;
        also deletes any steps not in the payload (mimicking full replace).
        """
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, pk, *args, **kwargs)

    def destroy(self, request, pk=None, *args, **kwargs):
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, pk, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="List Meals (subscription required for non-admins)",
        responses={
            200: MealListSerializer(many=True),
            403: openapi.Response(
                description="Subscription required",
                examples={
                    "application/json": {
                        "error": "Please upgrade your subscription to access meals.",
                        "subscription_options_url": "/api/subscriptions/options/"
                    }
                }
            )
        }
    )
    def list(self, request, *args, **kwargs):
        user = request.user
        # Allow admins to bypass subscription and program checks
        if not (user.is_staff or user.is_superuser):
            user_program = UserProgram.objects.filter(user=user, is_active=True).first()
            if not user_program or not UserSubscription.objects.filter(
                user=user, is_active=True, end_date__gte=timezone.now().date()
            ).exists():
                return Response(
                    {
                        "error": _("Please upgrade your subscription to access meals."),
                        "subscription_options_url": request.build_absolute_uri("/api/subscriptions/options/")
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Retrieve a single Meal (subscription required for non-admins)",
        responses={
            200: MealDetailSerializer(),
            403: openapi.Response(
                description="Subscription required",
                examples={
                    "application/json": {
                        "error": "Please upgrade your subscription to access meals.",
                        "subscription_options_url": "/api/subscriptions/options/"
                    }
                }
            ),
            404: openapi.Response(description="Meal not found")
        }
    )
    def retrieve(self, request, pk=None, *args, **kwargs):
        user = request.user
        # Check if the meal is accessible (for non-admins)
        instance = self.get_object()  # This uses get_queryset
        if not instance and not (user.is_staff or user.is_superuser):
            user_program = UserProgram.objects.filter(user=user, is_active=True).first()
            if user_program:
                has_active_subscription = UserSubscription.objects.filter(
                    user=user,
                    is_active=True,
                    end_date__gte=timezone.now().date()
                ).exists()
                if not has_active_subscription:
                    return Response(
                        {
                            "error": _("Please upgrade your subscription to access meals."),
                            "subscription_options_url": request.build_absolute_uri("/api/subscriptions/options/")
                        },
                        status=status.HTTP_403_FORBIDDEN
                    )

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @swagger_auto_schema(
        method='patch',
        operation_description="Upload or replace the Meal's food_photo (admins only).",
        consumes=['multipart/form-data'],
        request_body=MealImageUploadSerializer,
        responses={200: "Meal photo updated"}
    )
    @action(detail=True, methods=['patch'], url_path='upload-photo', parser_classes=[MultiPartParser, FormParser])
    def upload_photo(self, request, pk=None):
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)
        meal = self.get_object()
        serializer = MealImageUploadSerializer(meal, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Meal photo updated."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MealStepViewSet(viewsets.ModelViewSet):
    """
    (Optional) Manage MealSteps individually.
    """
    queryset = MealSteps.objects.all()
    serializer_class = MealStepListSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            context['language'] = self.request.user.language
        else:
            context['language'] = self.request.query_params.get('lang', 'en')
        return context

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return MealSteps.objects.none()

        user = self.request.user
        if user.is_staff:
            return MealSteps.objects.all()

        user_program = UserProgram.objects.filter(user=user, is_active=True).first()
        if not user_program or not user_program.is_subscription_active():
            return MealSteps.objects.none()

        # Only return steps for meals the user has access to
        accessible_meals = Meal.objects.filter(
            sessions__program=user_program.program,
            goal_type=user.goal
        ).values_list('id', flat=True)

        meal_id = self.request.query_params.get('meal_id')
        if meal_id:
            return self.queryset.filter(meal_id=meal_id, meal_id__in=accessible_meals)
        return self.queryset.filter(meal_id__in=accessible_meals)


class MealCompletionViewSet(viewsets.ModelViewSet):
    queryset = MealCompletion.objects.all()
    serializer_class = MealCompletionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return MealCompletion.objects.none()
        return MealCompletion.objects.filter(
            user=self.request.user,
            meal__goal_type=self.request.user.goal
        )
    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            context['language'] = self.request.user.language
        else:
            context['language'] = self.request.query_params.get('lang', 'en')
        return context





class CompleteMealView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        tags=['Meal Completions'],
        operation_description=_("Complete a meal."),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "session_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="ID of the Session"),
                "meal_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="ID of the Meal")
            },
            required=["session_id", "meal_id"],
            description="Payload for completing a meal."
        ),
        consumes=['application/json'],
        responses={201: MealCompletionSerializer()}
    )
    def post(self, request):
        serializer = CompleteMealSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        session_id = serializer.validated_data.get('session_id')
        meal_id = serializer.validated_data.get('meal_id')
        session = Session.objects.filter(id=session_id).first()
        if not session:
            return Response({"error": _("Session not found.")}, status=status.HTTP_400_BAD_REQUEST)
        meal = Meal.objects.filter(id=meal_id).first()
        if not meal:
            return Response({"error": _("Meal not found.")}, status=status.HTTP_400_BAD_REQUEST)

        # # Check if the meal's goal_type matches the user's goal
        # if meal.goal_type != request.user.goal:
        #     return Response({"error": _("This meal does not match your goal.")}, status=status.HTTP_400_BAD_REQUEST)

        user_program = UserProgram.objects.filter(user=request.user, is_active=True).first()
        if not user_program or not user_program.is_subscription_active():
            return Response({"error": _("Your subscription has ended. Please renew.")},
                            status=status.HTTP_403_FORBIDDEN)
        meal_completion = MealCompletion.objects.filter(session_id=session_id, meal_id=meal_id,
                                                        user=request.user).first()
        if not meal_completion:
            return Response({"error": _("Session and Meal combination not found.")}, status=status.HTTP_404_NOT_FOUND)
        if meal_completion.is_completed:
            return Response({"message": _("This meal has already been completed.")}, status=status.HTTP_200_OK)

        # Mark the meal as completed
        meal_completion.is_completed = True
        meal_completion.completion_date = now().date()
        meal_completion.save()

        # Check and mark session as completed if conditions are met
        session_completed = maybe_mark_session_completed(request.user, session)

        return Response({
            "message": _("Meal completed successfully."),
            "meal_completion": MealCompletionSerializer(meal_completion).data,
            "preparation_time": meal.preparation_time,
            "calories": meal.calories,
            "session_completed": session_completed
        }, status=status.HTTP_200_OK)


class UserDailyMealsView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]


    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            context['language'] = self.request.user.language
        else:
            context['language'] = self.request.query_params.get('lang', 'en')
        return context


    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Retrieve all meals assigned to the user for today."),
        responses={
            200: openapi.Response(
                description="User's daily meals",
                examples={"application/json": {"meals": [{"id": 1, "food_name": "Chicken Salad"}]}}
            ),
            403: openapi.Response(description="Subscription expired"),
            404: openapi.Response(description="No meals found for today")
        }
    )
    def get(self, request):
        today = localdate()
        user = request.user
        user_program = UserProgram.objects.filter(user=user, is_active=True).first()
        if not user_program or not user_program.is_subscription_active():
            return Response({"error": _("Your subscription has ended. Please renew.")},
                            status=status.HTTP_403_FORBIDDEN)
        user_sessions = SessionCompletion.objects.filter(user=user, is_completed=True,
                                                         completion_date=today).values_list('session_id', flat=True)
        if not user_sessions:
            return Response({"message": _("No sessions found for today.")}, status=status.HTTP_404_NOT_FOUND)
        meals = Meal.objects.filter(
            sessions__id__in=user_sessions,
            goal_type=user.goal  # Add this filter
        ).distinct()
        if not meals.exists():
            return Response({"message": _("No meals found for today.")}, status=status.HTTP_404_NOT_FOUND)
        serializer = MealDetailSerializer(meals, many=True,
                                          context={"language": getattr(user, 'language', 'en'), "request": request})
        return Response({"meals": serializer.data}, status=status.HTTP_200_OK)

class MealDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]



    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            context['language'] = self.request.user.language
        else:
            context['language'] = self.request.query_params.get('lang', 'en')
        return context

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Retrieve detailed info about a specific meal."),
        manual_parameters=[
            openapi.Parameter(
                'meal_id',
                openapi.IN_PATH,
                description="ID of the meal to retrieve details",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        responses={
            200: openapi.Response(description="Meal details retrieved successfully."),
            404: openapi.Response(description="Meal not found.")
        }
    )
    def get(self, request, meal_id):
        user = request.user
        user_program = UserProgram.objects.filter(user=user, is_active=True).first()
        if not user_program or not user_program.is_subscription_active():
            return Response({"error": _("Your subscription has ended. Please renew.")},
                            status=status.HTTP_403_FORBIDDEN)

        meal = Meal.objects.prefetch_related('steps').filter(
            id=meal_id,
            goal_type=user.goal,
            sessions__program=user_program.program
        ).first()
        if not meal:
            return Response({"error": _("Meal not found or not accessible.")}, status=status.HTTP_404_NOT_FOUND)
        serializer = MealDetailSerializer(meal, context={"language": getattr(request.user, 'language', 'en'),
                                                         "request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
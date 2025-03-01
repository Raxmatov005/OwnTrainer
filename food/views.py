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


from users_app.models import Meal, MealSteps, MealCompletion, SessionCompletion, Session, UserProgram
from food.serializers import (
    MealNestedSerializer,
    MealCompletionSerializer,
    CompleteMealSerializer,
    MealDetailSerializer,
    MealStepSerializer,

)

class MealViewSet(viewsets.ModelViewSet):
    """
    Admins can create/update. Non-admins (with subscription) can read.
    We define create/update/partial_update with form-data via manual_parameters,
    so drf-yasg won't conflict.
    """
    queryset = Meal.objects.all()
    serializer_class = MealNestedSerializer
    permission_classes = [IsAuthenticated]  # Or a custom IsAdminOrReadOnly
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Meal.objects.none()

        user = self.request.user
        if not user.is_authenticated:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(_("Authentication is required to view meals."))

        if user.is_staff:
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

        return Meal.objects.filter(sessions__program=user_program.program).distinct().prefetch_related("steps")

    def get_serializer_context(self):
        language = self.request.query_params.get('lang', 'en')
        return {
            **super().get_serializer_context(),
            "language": language,
            "request": self.request
        }

    # ---------------------------------------------
    # LIST, RETRIEVE (pure read ops, no changes here)
    # ---------------------------------------------
    @swagger_auto_schema(
        tags=['Meals'],
        operation_description="List all meals (only for staff or valid subscription user).",
        responses={200: MealNestedSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(qs, many=True)
        return Response({"meals": serializer.data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description="Retrieve a meal by ID (staff or subscription).",
        responses={200: MealNestedSerializer()}
    )
    def retrieve(self, request, pk=None):
        meal = self.get_object()
        serializer = self.get_serializer(meal)
        return Response({"meal": serializer.data}, status=status.HTTP_200_OK)

    # ---------------------------------------------
    # CREATE (multipart/form-data, manual parameters)
    # ---------------------------------------------
    @swagger_auto_schema(
        tags=['Meals'],
        operation_description="Create a new Meal (admins only) with optional 'food_photo' and nested steps. "
                              "Send everything as multipart/form-data. For `steps`, pass a JSON string. "
                              "Example: steps=[{\"title\":\"Step1\",\"text\":\"desc\"}, ...]. ",
        request_body=None,
        consumes=["multipart/form-data"],
        manual_parameters=[
            openapi.Parameter(
                name='meal_type',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Meal type (e.g. breakfast, lunch, etc.)"
            ),
            openapi.Parameter(
                name='food_name',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Name of the food"
            ),
            openapi.Parameter(
                name='calories',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Caloric content"
            ),
            openapi.Parameter(
                name='water_content',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Water content in ml"
            ),
            openapi.Parameter(
                name='food_photo',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description="Optional meal photo"
            ),
            openapi.Parameter(
                name='preparation_time',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_INTEGER,
                description="Preparation time (minutes)"
            ),
            openapi.Parameter(
                name='description',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Meal description"
            ),
            openapi.Parameter(
                name='video_url',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Optional video URL"
            ),
            openapi.Parameter(
                name='steps',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="JSON array of step objects. e.g. [{\"title\":\"\",\"text\":\"\",\"step_time\":\"\"}]"
            ),
        ],
        responses={
            201: openapi.Response(description="Meal created", schema=MealNestedSerializer())
        }
    )
    def create(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    # ---------------------------------------------
    # UPDATE (multipart/form-data, manual parameters)
    # ---------------------------------------------
    @swagger_auto_schema(
        tags=['Meals'],
        operation_description="Update a Meal (admins only). You can upload a new `food_photo`. Steps are updated/created as provided. "
                              "Send everything as multipart/form-data. For `steps`, pass a JSON array string. "
                              "If a step includes 'id', that step is updated; otherwise new steps are created.",
        request_body=None,
        consumes=["multipart/form-data"],
        manual_parameters=[
            openapi.Parameter(
                name='meal_type',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Updated meal type"
            ),
            openapi.Parameter(
                name='food_name',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Updated food name"
            ),
            openapi.Parameter(
                name='calories',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Updated calories"
            ),
            openapi.Parameter(
                name='water_content',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Updated water_content in ml"
            ),
            openapi.Parameter(
                name='food_photo',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description="Replace or upload new meal photo"
            ),
            openapi.Parameter(
                name='preparation_time',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_INTEGER,
                description="Updated prep time in minutes"
            ),
            openapi.Parameter(
                name='description',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Updated meal description"
            ),
            openapi.Parameter(
                name='video_url',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Updated video URL"
            ),
            openapi.Parameter(
                name='steps',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="JSON array of steps. e.g. [{\"id\":123, \"title\":\"UpdatedTitle\"}, ...]"
            ),
        ],
        responses={
            200: openapi.Response(description="Meal updated", schema=MealNestedSerializer())
        }
    )
    def update(self, request, pk=None, *args, **kwargs):
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, pk, *args, **kwargs)

    # ---------------------------------------------
    # PARTIAL UPDATE
    # ---------------------------------------------
    @swagger_auto_schema(
        method='patch',
        tags=['Meals'],
        operation_description="Partially update a Meal (admins only). You can update just certain fields, including uploading a new `food_photo`. "
                              "Send multipart/form-data. For steps, pass a JSON array string if you want to update them. "
                              "If a step item includes 'id', that step is updated; otherwise new steps are created.",
        request_body=None,
        consumes=['multipart/form-data'],
        manual_parameters=[
            openapi.Parameter(
                name='meal_type',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Updated meal type (optional)"
            ),
            openapi.Parameter(
                name='food_name',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Updated food name"
            ),
            openapi.Parameter(
                name='calories',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Updated calories"
            ),
            openapi.Parameter(
                name='water_content',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Updated water content in ml"
            ),
            openapi.Parameter(
                name='food_photo',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description="Replace or upload new meal photo"
            ),
            openapi.Parameter(
                name='preparation_time',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_INTEGER,
                description="Updated preparation time"
            ),
            openapi.Parameter(
                name='description',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Updated meal description"
            ),
            openapi.Parameter(
                name='video_url',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="Updated video URL"
            ),
            openapi.Parameter(
                name='steps',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                description="JSON array of steps to create/update. e.g. [{\"id\":123,\"title\":\"newTitle\"},...]"
            ),
        ],
        responses={
            200: openapi.Response(
                description="Meal partially updated",
                schema=MealNestedSerializer()
            )
        }
    )
    @action(detail=True, methods=['patch'], url_path='partial-update', parser_classes=[MultiPartParser, FormParser])
    def partial_update_meal(self, request, pk=None):
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, pk, *args, **kwargs)

    # ---------------------------------------------
    # DESTROY
    # ---------------------------------------------
    @swagger_auto_schema(
        tags=['Meals'],
        operation_description="Delete a Meal by ID (admins only).",
        responses={204: "No Content"}
    )
    def destroy(self, request, pk=None, *args, **kwargs):
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, pk, *args, **kwargs)

    # ---------------------------------------------
    # (Optional) UPLOAD PHOTO ENDPOINT
    # ---------------------------------------------
    @swagger_auto_schema(
        method='patch',
        tags=['Meals'],
        operation_description="Upload or update the Meal's 'food_photo' separately (admins only).",
        consumes=['multipart/form-data'],
        manual_parameters=[
            openapi.Parameter(
                name="food_photo",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description="New meal photo"
            )
        ],
        responses={
            200: openapi.Response(
                description="Successfully updated meal photo",
                schema=MealNestedSerializer()
            )
        }
    )
    @action(detail=True, methods=['patch'], url_path='upload-photo', parser_classes=[MultiPartParser, FormParser])
    def upload_photo(self, request, pk=None):
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)

        meal = self.get_object()
        file_obj = request.FILES.get('food_photo', None)
        if not file_obj:
            return Response({"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        meal.food_photo = file_obj
        meal.save()
        serializer = self.get_serializer(meal)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MealStepViewSet(viewsets.ModelViewSet):
    """
    (Optional) Manage MealSteps individually.
    """
    queryset = MealSteps.objects.all()
    serializer_class = MealStepSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['language'] = self.request.query_params.get('lang', 'en')
        context['request'] = self.request
        return context

    def get_queryset(self):
        meal_id = self.request.query_params.get('meal_id')
        if meal_id:
            return self.queryset.filter(meal_id=meal_id)
        return self.queryset

class MealCompletionViewSet(viewsets.ModelViewSet):
    queryset = MealCompletion.objects.all()
    serializer_class = MealCompletionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return MealCompletion.objects.none()
        return MealCompletion.objects.filter(user=self.request.user)

    def get_serializer_context(self):
        language = self.request.query_params.get('lang', 'en')
        return {**super().get_serializer_context(), "language": language}

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
        user_program = UserProgram.objects.filter(user=request.user, is_active=True).first()
        if not user_program or not user_program.is_subscription_active():
            return Response({"error": _("Your subscription has ended. Please renew.")},
                            status=status.HTTP_403_FORBIDDEN)
        meal_completion = MealCompletion.objects.filter(session_id=session_id, meal_id=meal_id, user=request.user).first()
        if not meal_completion:
            return Response({"error": _("Session and Meal combination not found.")}, status=status.HTTP_404_NOT_FOUND)
        if meal_completion.is_completed:
            return Response({"message": _("This meal has already been completed.")}, status=status.HTTP_200_OK)
        meal_completion.is_completed = True
        meal_completion.completion_date = now().date()
        meal_completion.save()
        return Response({
            "message": _("Meal completed successfully."),
            "meal_completion": MealCompletionSerializer(meal_completion).data
        }, status=status.HTTP_200_OK)

class UserDailyMealsView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

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
            return Response({"error": _("Your subscription has ended. Please renew.")}, status=status.HTTP_403_FORBIDDEN)
        user_sessions = SessionCompletion.objects.filter(user=user, session_date=today).values_list('session_id', flat=True)
        if not user_sessions:
            return Response({"message": _("No sessions found for today.")}, status=status.HTTP_404_NOT_FOUND)
        meals = Meal.objects.filter(sessions__id__in=user_sessions).distinct()
        if not meals.exists():
            return Response({"message": _("No meals found for today.")}, status=status.HTTP_404_NOT_FOUND)
        serializer = MealDetailSerializer(meals, many=True, context={"language": getattr(user, 'language', 'en'), "request": request})
        return Response({"meals": serializer.data}, status=status.HTTP_200_OK)

class MealDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

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
        meal = Meal.objects.prefetch_related('steps').filter(id=meal_id).first()
        if not meal:
            return Response({"error": _("Meal not found.")}, status=status.HTTP_404_NOT_FOUND)
        serializer = MealDetailSerializer(meal, context={"language": getattr(request.user, 'language', 'en'), "request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

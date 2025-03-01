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
    Handles CRUD for Meal along with nested MealSteps.
    Nested update logic will:
      - update existing steps (if an 'id' is provided),
      - create new ones for any item without an 'id',
      - leave unmentioned steps intact.
    """
    queryset = Meal.objects.all()
    serializer_class = MealNestedSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            # drf-yasg view
            return Meal.objects.none()

        user = self.request.user
        if not user.is_authenticated:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(_("Authentication is required to view meals."))

        # If user is staff, show all meals
        if user.is_staff:
            return Meal.objects.all().prefetch_related("steps")

        # Otherwise, filter by user's active program & subscription
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

        # Show meals for sessions in the user's program
        return Meal.objects.filter(sessions__program=user_program.program).distinct().prefetch_related("steps")

    def get_serializer_context(self):
        language = self.request.query_params.get('lang', 'en')
        return {
            **super().get_serializer_context(),
            "language": language,
            "request": self.request
        }

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("List all meals for the authenticated user"),
        responses={200: MealNestedSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({"meals": serializer.data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Retrieve a specific meal by ID"),
        responses={200: MealNestedSerializer()}
    )
    def retrieve(self, request, pk=None):
        meal = self.get_object()
        serializer = self.get_serializer(meal)
        return Response({"meal": serializer.data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Create a new meal with optional steps. You can upload a 'food_photo' in the same request."),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'meal_type': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=[choice[0] for choice in Meal.MEAL_TYPES],
                    description="Type of the meal (e.g., 'breakfast', 'lunch', 'snack', 'dinner')"
                ),
                'food_name': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Name of the food"
                ),
                'calories': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Caloric content (decimal as string)"
                ),
                'water_content': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Water content in ml (decimal as string)"
                ),
                'food_photo': openapi.Schema(
                    type=openapi.TYPE_FILE,
                    description="Optional photo of the food"
                ),
                'preparation_time': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="Preparation time in minutes"
                ),
                'description': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Description of the meal"
                ),
                'video_url': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_URI,
                    description="Optional URL to a video"
                ),
                'steps': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'title': openapi.Schema(type=openapi.TYPE_STRING, description="Step title"),
                            'text': openapi.Schema(type=openapi.TYPE_STRING, description="Step description"),
                            'step_time': openapi.Schema(type=openapi.TYPE_STRING, description="Time for this step")
                        }
                    ),
                    description="List of preparation steps"
                ),
            },
            required=['meal_type', 'food_name', 'calories', 'water_content', 'preparation_time']
        ),
        consumes=['multipart/form-data'],
        responses={
            201: openapi.Response(description="Meal created", schema=MealNestedSerializer()),
            400: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'error': openapi.Schema(type=openapi.TYPE_STRING, description='Error message')
                }
            )
        }
    )
    def create(self, request, *args, **kwargs):
        """Create a Meal (and optional Steps) with a possible file upload for food_photo."""
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Update a Meal by ID. You can upload a new 'food_photo' in the same request."),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'meal_type': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=[choice[0] for choice in Meal.MEAL_TYPES]
                ),
                'food_name': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Name of the food"
                ),
                'calories': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Caloric content (decimal as string)"
                ),
                'water_content': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Water content in ml (decimal as string)"
                ),
                'food_photo': openapi.Schema(
                    type=openapi.TYPE_FILE,
                    description="Upload a new photo of the food (optional)"
                ),
                'preparation_time': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="Preparation time in minutes"
                ),
                'description': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Description of the meal"
                ),
                'video_url': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_URI,
                    description="Optional video URL"
                ),
                'steps': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(
                                type=openapi.TYPE_INTEGER,
                                description="If provided, update this existing step. Otherwise, create a new step."
                            ),
                            'title': openapi.Schema(type=openapi.TYPE_STRING, description="Step title"),
                            'text': openapi.Schema(type=openapi.TYPE_STRING, description="Step description"),
                            'step_time': openapi.Schema(type=openapi.TYPE_STRING, description="Time for this step")
                        }
                    )
                ),
            }
        ),
        consumes=['multipart/form-data'],
        responses={
            200: openapi.Response(description="Meal updated", schema=MealNestedSerializer())
        }
    )
    def update(self, request, pk=None, *args, **kwargs):
        """Full update of a Meal. Replace or add steps, optionally upload a new food_photo."""
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Partially update a Meal by ID (JSON or form-data)."),
        request_body=MealNestedSerializer,
        responses={200: MealNestedSerializer()}
    )
    def partial_update(self, request, pk=None, *args, **kwargs):
        """
        Partially update a Meal.
        NOTE: If you want to upload a file in partial_update, set Content-Type: multipart/form-data
        and pass only the fields you want to update.
        """
        return super().partial_update(request, pk, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Delete a Meal by ID"),
        responses={204: "No Content"}
    )
    def destroy(self, request, pk=None, *args, **kwargs):
        """Delete a Meal."""
        return super().destroy(request, pk, *args, **kwargs)

    # -----------------------------------------------------------
    # Custom action to upload or update the meal's food_photo only
    # -----------------------------------------------------------
    @swagger_auto_schema(
        method='patch',
        tags=['Meals'],
        operation_description=_("Upload or update the Meal's 'food_photo' separately."),
        consumes=['multipart/form-data'],
        manual_parameters=[
            openapi.Parameter(
                name="food_photo",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description="Upload the food photo"
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
        """
        Separate endpoint for uploading/replacing the Meal's food_photo.
        """
        meal = self.get_object()
        file_obj = request.FILES.get('food_photo', None)
        if not file_obj:
            return Response({"detail": "No photo uploaded."}, status=status.HTTP_400_BAD_REQUEST)

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

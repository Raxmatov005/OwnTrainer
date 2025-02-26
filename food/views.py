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
    MealCreateSerializer
)


class MealViewSet(viewsets.ModelViewSet):
    """
    Handles CRUD for Meal along with nested MealSteps.
    """
    queryset = Meal.objects.all()
    permission_classes = [IsAuthenticated]
    # Always include MultiPartParser for all actions
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        """Return appropriate serializer class based on the action"""
        if self.action in ['create', 'update', 'partial_update']:
            return MealCreateSerializer
        return MealNestedSerializer

    def get_serializer_context(self):
        language = self.request.query_params.get('lang', 'en')
        return {**super().get_serializer_context(), "language": language, "request": self.request}

    def get_queryset(self):
        # Your existing queryset logic
        if getattr(self, 'swagger_fake_view', False):
            return Meal.objects.none()
        if not self.request.user.is_authenticated:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(_("Authentication is required to view meals."))
        if self.request.user.is_staff:
            return Meal.objects.all().prefetch_related("steps")
        from users_app.models import UserProgram, UserSubscription
        user_program = UserProgram.objects.filter(user=self.request.user, is_active=True).first()
        if not user_program:
            return Meal.objects.none()
        has_active_subscription = UserSubscription.objects.filter(
            user=self.request.user,
            is_active=True,
            end_date__gte=timezone.now().date()
        ).exists()
        if not has_active_subscription:
            return Meal.objects.none()
        return Meal.objects.filter(sessions__program=user_program.program).distinct().prefetch_related("steps")

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("List all meals for the authenticated user"),
        responses={200: MealNestedSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = MealNestedSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response({"meals": serializer.data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Retrieve a specific meal"),
        responses={200: MealNestedSerializer()}
    )
    def retrieve(self, request, pk=None):
        meal = self.get_object()
        serializer = MealNestedSerializer(meal, context=self.get_serializer_context())
        return Response({"meal": serializer.data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Create a new meal with associated steps and a required food photo."),
        manual_parameters=[
            openapi.Parameter(
                'food_photo',
                openapi.IN_FORM,
                description="Required photo of the food",
                type=openapi.TYPE_FILE,
                required=True
            ),
            openapi.Parameter(
                'meal_type',
                openapi.IN_FORM,
                description="Type of the meal (e.g., breakfast, lunch)",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'food_name',
                openapi.IN_FORM,
                description="Name of the food",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'calories',
                openapi.IN_FORM,
                description="Caloric content (decimal as string)",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'water_content',
                openapi.IN_FORM,
                description="Water content in ml (decimal as string)",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'preparation_time',
                openapi.IN_FORM,
                description="Preparation time in minutes",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                'description',
                openapi.IN_FORM,
                description="Description of the meal",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'video_url',
                openapi.IN_FORM,
                description="Optional URL to a video",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'steps',
                openapi.IN_FORM,
                description="JSON array of preparation steps",
                type=openapi.TYPE_STRING,
                required=False
            ),
        ],
        consumes=['multipart/form-data'],
        responses={
            201: MealNestedSerializer()
        }
    )
    def create(self, request, *args, **kwargs):
        # Print debug information
        print("CREATE VIEW - Request DATA:", request.data)
        print("CREATE VIEW - Request FILES:", request.FILES)

        # Handle 'steps' JSON string if provided
        data = request.data.copy()
        if 'steps' in data and isinstance(data['steps'], str):
            try:
                data['steps'] = json.loads(data['steps'])
            except json.JSONDecodeError:
                return Response(
                    {"steps": ["Invalid JSON format"]},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Create serializer with the processed data
        serializer = MealCreateSerializer(data=data, context=self.get_serializer_context())

        if serializer.is_valid():
            meal = serializer.save()
            return Response({
                "message": _("Meal created successfully"),
                "meal": MealNestedSerializer(meal, context=self.get_serializer_context()).data
            }, status=status.HTTP_201_CREATED)

        # If validation failed, print errors and return response
        print("Serializer errors:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Update an existing meal."),
        manual_parameters=[
            openapi.Parameter(
                'food_photo',
                openapi.IN_FORM,
                description="Photo of the food (optional for update)",
                type=openapi.TYPE_FILE,
                required=False
            ),
            # Include all other parameters similar to create method
            openapi.Parameter(
                'meal_type',
                openapi.IN_FORM,
                description="Type of the meal (e.g., breakfast, lunch)",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'food_name',
                openapi.IN_FORM,
                description="Name of the food",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'calories',
                openapi.IN_FORM,
                description="Caloric content (decimal as string)",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'water_content',
                openapi.IN_FORM,
                description="Water content in ml (decimal as string)",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'preparation_time',
                openapi.IN_FORM,
                description="Preparation time in minutes",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'description',
                openapi.IN_FORM,
                description="Description of the meal",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'video_url',
                openapi.IN_FORM,
                description="Optional URL to a video",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'steps',
                openapi.IN_FORM,
                description="JSON array of preparation steps",
                type=openapi.TYPE_STRING,
                required=False
            ),
        ],
        consumes=['multipart/form-data'],
        responses={
            200: MealNestedSerializer()
        }
    )
    def update(self, request, pk=None, *args, **kwargs):
        meal = self.get_object()

        # Print debug information
        print("UPDATE VIEW - Request DATA:", request.data)
        print("UPDATE VIEW - Request FILES:", request.FILES)

        # Handle 'steps' JSON string if provided
        data = request.data.copy()
        if 'steps' in data and isinstance(data['steps'], str):
            try:
                data['steps'] = json.loads(data['steps'])
            except json.JSONDecodeError:
                return Response(
                    {"steps": ["Invalid JSON format"]},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Set partial=True for PATCH method
        partial = kwargs.pop('partial', False)

        serializer = MealCreateSerializer(
            meal,
            data=data,
            partial=partial,
            context=self.get_serializer_context()
        )

        if serializer.is_valid():
            meal = serializer.save()
            return Response({
                "message": _("Meal updated successfully"),
                "meal": MealNestedSerializer(meal, context=self.get_serializer_context()).data
            }, status=status.HTTP_200_OK)

        # If validation failed, print errors and return response
        print("Serializer errors:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Delete a meal"),
        responses={204: "No Content"}
    )
    def destroy(self, request, *args, **kwargs):
        meal = self.get_object()
        meal.delete()
        return Response({"message": _("Meal deleted successfully")}, status=status.HTTP_204_NO_CONTENT)



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

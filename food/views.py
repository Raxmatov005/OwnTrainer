from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework.views import APIView
from users_app.models import Preparation, Meal, MealCompletion, SessionCompletion, Session, PreparationSteps, UserProgram
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils.translation import gettext_lazy as _
from googletrans import Translator
from food.serializers import (
    MealNestedSerializer,
    MealCompletionSerializer,
    NestedPreparationSerializer,
    CompleteMealSerializer,
    MealDetailSerializer,
    NestedPreparationStepSerializer,
EmptyQuerySerializer
)
from rest_framework.exceptions import PermissionDenied
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.timezone import localdate, now


translator = Translator()

def translate_text(text, target_language):
    try:
        translation = translator.translate(text, dest=target_language)
        return translation.text
    except Exception as e:
        print(f"Translation error: {e}")
        return text

from rest_framework.parsers import MultiPartParser, JSONParser
from drf_yasg import openapi

class MealViewSet(viewsets.ModelViewSet):
    queryset = Meal.objects.all()
    serializer_class = MealNestedSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # ✅ Moved here


    def get_parser_classes(self):
        """✅ Ensure correct parser for each action"""
        if self.action in ['create', 'update', 'partial_update']:
            return [JSONParser]  # JSON-based API
        elif self.action == 'upload_image':
            return [MultiPartParser]  # For file uploads
        return super().get_parser_classes()
    def get_serializer_context(self):
        language = self.request.query_params.get('lang', 'en')
        return {**super().get_serializer_context(), "language": language}

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Meal.objects.none()
        if not self.request.user.is_authenticated:
            raise PermissionDenied(_("Authentication is required to view meals."))
        user_program = UserProgram.objects.filter(user=self.request.user, is_active=True).first()
        if not user_program or not user_program.is_subscription_active():
            return Meal.objects.none()
        if not self.request.user.is_staff:
            sessions = SessionCompletion.objects.filter(user=self.request.user).values_list('session_id', flat=True)
            return Meal.objects.filter(sessions__id__in=sessions).distinct()
        return Meal.objects.all()

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("List all meals for the authenticated user"),
        responses={200: MealNestedSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({"meals": serializer.data})

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Retrieve a specific meal"),
        responses={200: MealNestedSerializer()},
    )
    def retrieve(self, request, pk=None):
        meal = self.get_object()
        serializer = self.get_serializer(meal)
        return Response({"meal": serializer.data})

    @swagger_auto_schema(
        tags=['Meals'],
        request_body=MealNestedSerializer,
        consumes=['multipart/form-data'],
        responses={201: MealNestedSerializer()}
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": _("Meal created successfully"),
                "meal": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Update a meal by ID"),
        request_body=MealNestedSerializer,
        responses={200: MealNestedSerializer()}
    )
    def update(self, request, pk=None, *args, **kwargs):
        meal = self.get_object()
        serializer = self.get_serializer(meal, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": _("Meal updated successfully"),
                "meal": serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Partially update a meal by ID"),
        request_body=MealNestedSerializer,
        responses={200: MealNestedSerializer()}
    )
    def partial_update(self, request, pk=None, *args, **kwargs):
        meal = self.get_object()
        serializer = self.get_serializer(meal, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": _("Meal partially updated successfully"),
                "meal": serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Delete a meal"),
        responses={204: "No Content"}
    )
    def destroy(self, request, pk=None, *args, **kwargs):
        meal = self.get_object()
        meal.delete()
        return Response({"message": _("Meal deleted successfully")}, status=status.HTTP_204_NO_CONTENT)

from drf_yasg import openapi
from rest_framework.parsers import JSONParser

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

    @swagger_auto_schema(
        tags=['Meal Completions'],
        operation_description=_("List all meal completions for the authenticated user"),
        responses={200: MealCompletionSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"meal_completions": serializer.data})

    @swagger_auto_schema(
        tags=['Meal Completions'],
        operation_description=_("Retrieve a specific meal completion"),
        responses={200: MealCompletionSerializer()}
    )
    def retrieve(self, request, pk=None):
        meal_completion = self.get_object()
        serializer = self.get_serializer(meal_completion)
        return Response({"meal_completion": serializer.data})

    @swagger_auto_schema(
        tags=['Meal Completions'],
        operation_description=_("Create a new meal completion"),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "session_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Session ID"),
                "meal_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Meal ID")
            },
            required=["session_id", "meal_id"],
            description="Payload for completing a meal."
        ),
        responses={201: MealCompletionSerializer()}
    )
    def create(self, request, *args, **kwargs):
        serializer = CompleteMealSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            session_id = serializer.validated_data.get('session_id')
            meal_id = serializer.validated_data.get('meal_id')

            # Ensure User Program is Active
            user_program = UserProgram.objects.filter(user=user, is_active=True).first()
            if not user_program or not user_program.is_subscription_active():
                return Response({"error": _("Your subscription has ended. Please renew.")}, status=status.HTTP_403_FORBIDDEN)

            # Ensure Session and Meal Exist
            if not Session.objects.filter(id=session_id).exists():
                return Response({"error": _("Invalid session ID.")}, status=status.HTTP_400_BAD_REQUEST)
            if not Meal.objects.filter(id=meal_id).exists():
                return Response({"error": _("Invalid meal ID.")}, status=status.HTTP_400_BAD_REQUEST)

            # Check if the meal is already completed
            meal_completion, created = MealCompletion.objects.get_or_create(
                user=user,
                session_id=session_id,
                meal_id=meal_id,
                defaults={"is_completed": True, "completion_date": now().date()}
            )

            if not created:
                return Response({"message": _("This meal has already been completed.")}, status=status.HTTP_200_OK)

            return Response({
                "message": _("Meal completion recorded successfully"),
                "meal_completion": MealCompletionSerializer(meal_completion, context={"language": request.user.language}).data,
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Meal Completions'],
        operation_description=_("Update meal completion status by ID"),
        request_body=MealCompletionSerializer,
        responses={200: MealCompletionSerializer()}
    )
    def update(self, request, pk=None, *args, **kwargs):
        meal_completion = self.get_object()
        serializer = self.get_serializer(meal_completion, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": _("Meal completion updated successfully"),
                "meal_completion": serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Meal Completions'],
        operation_description=_("Partially update a meal completion record"),
        request_body=MealCompletionSerializer,
        responses={200: MealCompletionSerializer()}
    )
    def partial_update(self, request, pk=None, *args, **kwargs):
        meal_completion = self.get_object()
        serializer = self.get_serializer(meal_completion, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": _("Meal completion record partially updated successfully"),
                "meal_completion": serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Meal Completions'],
        operation_description=_("Delete a meal completion record"),
        responses={204: "No Content"}
    )
    def destroy(self, request, pk=None, *args, **kwargs):
        meal_completion = self.get_object()
        meal_completion.delete()
        return Response({"message": _("Meal completion record deleted successfully")}, status=status.HTTP_204_NO_CONTENT)

from drf_yasg import openapi
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext_lazy as _
from food.serializers import NestedPreparationSerializer, NestedPreparationStepSerializer
from users_app.models import Preparation, Meal

class PreparationViewSet(viewsets.ModelViewSet):
    queryset = Preparation.objects.all()
    serializer_class = NestedPreparationSerializer
    permission_classes = [IsAuthenticated]

    def get_parser_classes(self):
        """✅ Correct method to specify parsers"""
        if self.action in ['create', 'update', 'partial_update']:
            return [JSONParser]  # JSON-based API
        return super().get_parser_classes()

    def get_queryset(self):
        meal_id = self.request.query_params.get('meal_id')
        if meal_id:
            if not Meal.objects.filter(id=meal_id).exists():
                return Preparation.objects.none()
            return self.queryset.filter(meal_id=meal_id)
        return self.queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['language'] = getattr(self.request.user, 'language', 'en')
        return context

    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description=_("Create a new preparation with steps."),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Name of the preparation"),
                "description": openapi.Schema(type=openapi.TYPE_STRING, description="Description"),
                "preparation_time": openapi.Schema(type=openapi.TYPE_INTEGER, description="Preparation time in minutes"),
                "calories": openapi.Schema(type=openapi.TYPE_NUMBER, description="Calories"),
                "water_usage": openapi.Schema(type=openapi.TYPE_NUMBER, description="Water usage"),
                "video_url": openapi.Schema(type=openapi.TYPE_STRING, description="Video URL"),
                "steps": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "title": openapi.Schema(type=openapi.TYPE_STRING, description="Step title"),
                            "text": openapi.Schema(type=openapi.TYPE_STRING, description="Step text"),
                            "step_time": openapi.Schema(type=openapi.TYPE_INTEGER, description="Step time in seconds")
                        },
                        required=["title", "text"],
                        description="A preparation step"
                    ),
                    description="List of preparation steps"
                )
            },
            required=["name", "preparation_time"],
            description="Payload for creating a new preparation."
        ),
        consumes=['application/json'],
        responses={201: NestedPreparationSerializer()}
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            preparation = serializer.save()

            # Validate and attach steps
            steps_data = request.data.get("steps", [])
            for step_data in steps_data:
                step_serializer = NestedPreparationStepSerializer(data=step_data, context=self.get_serializer_context())
                if step_serializer.is_valid():
                    step_serializer.save(preparation=preparation)
                else:
                    return Response(step_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                "message": _("Preparation created successfully"),
                "preparation": serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description=_("Update an existing preparation completely."),
        request_body=NestedPreparationSerializer,
        responses={200: NestedPreparationSerializer()}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description=_("Partially update a preparation."),
        request_body=NestedPreparationSerializer,
        responses={200: NestedPreparationSerializer()}
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description=_("Delete a preparation by ID."),
        responses={204: "No Content"}
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description=_("Filter preparations by meal ID."),
        manual_parameters=[
            openapi.Parameter(
                'meal_id',
                openapi.IN_QUERY,
                description="ID of the meal to filter preparations.",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        responses={200: NestedPreparationSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='by-meal')
    def get_by_meal(self, request):
        meal_id = request.query_params.get('meal_id')
        if not meal_id:
            return Response({"error": _("meal_id is required.")}, status=status.HTTP_400_BAD_REQUEST)

        if not Meal.objects.filter(id=meal_id).exists():
            return Response({"error": _("Meal not found.")}, status=status.HTTP_404_NOT_FOUND)

        preparations = self.get_queryset().filter(meal_id=meal_id)
        serializer = self.get_serializer(preparations, many=True)
        return Response({"preparations": serializer.data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description=_("Translate preparation fields into multiple languages if missing."),
        responses={200: {"message": _("Fields translated successfully.")}, 404: "Not Found"}
    )
    @action(detail=True, methods=['post'], url_path='translate')
    def translate_fields(self, request, pk=None):
        preparation = self.get_object()

        # Only translate if fields are missing
        if not preparation.name_uz:
            preparation.name_uz = translate_text(preparation.name, 'uz')
        if not preparation.name_ru:
            preparation.name_ru = translate_text(preparation.name, 'ru')
        if not preparation.name_en:
            preparation.name_en = translate_text(preparation.name, 'en')

        if not preparation.description_uz:
            preparation.description_uz = translate_text(preparation.description, 'uz')
        if not preparation.description_ru:
            preparation.description_ru = translate_text(preparation.description, 'ru')
        if not preparation.description_en:
            preparation.description_en = translate_text(preparation.description, 'en')

        preparation.save()
        return Response({"message": _("Fields translated successfully.")}, status=status.HTTP_200_OK)

from drf_yasg import openapi
from rest_framework.parsers import JSONParser
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext_lazy as _
from food.serializers import NestedPreparationStepSerializer
from users_app.models import PreparationSteps, Preparation

class PreparationStepViewSet(viewsets.ModelViewSet):
    queryset = PreparationSteps.objects.all()
    serializer_class = NestedPreparationStepSerializer
    permission_classes = [IsAuthenticated]

    def get_parser_classes(self):
        """✅ Correct method to specify parsers"""
        if self.action in ['create', 'update', 'partial_update']:
            return [JSONParser]  # JSON-based API
        return super().get_parser_classes()

    def get_queryset(self):
        preparation_id = self.request.query_params.get('preparation_id')
        if preparation_id:
            if not Preparation.objects.filter(id=preparation_id).exists():
                return PreparationSteps.objects.none()
            return self.queryset.filter(preparation_id=preparation_id)
        return self.queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['language'] = getattr(self.request.user, 'language', 'en')
        return context

    @swagger_auto_schema(
        tags=['Preparation Steps'],
        operation_description=_("Create a new preparation step."),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "preparation_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="ID of the Preparation"),
                "title": openapi.Schema(type=openapi.TYPE_STRING, description="Step title"),
                "text": openapi.Schema(type=openapi.TYPE_STRING, description="Step text"),
                "step_time": openapi.Schema(type=openapi.TYPE_INTEGER, description="Step time in seconds"),
            },
            required=["preparation_id", "title", "text"],
            description="Payload for creating a new preparation step."
        ),
        consumes=['application/json'],
        responses={201: NestedPreparationStepSerializer()}
    )
    def create(self, request, *args, **kwargs):
        preparation_id = request.data.get("preparation_id")

        # Check if preparation exists
        preparation = Preparation.objects.filter(id=preparation_id).first()
        if not preparation:
            return Response({"error": _("Invalid preparation ID.")}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            step = serializer.save(preparation=preparation)
            return Response({
                "message": _("Preparation step created successfully"),
                "preparation_step": NestedPreparationStepSerializer(step).data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Preparation Steps'],
        operation_description=_("Update a preparation step"),
        request_body=NestedPreparationStepSerializer,
        responses={200: NestedPreparationStepSerializer()}
    )
    def update(self, request, *args, **kwargs):
        step = self.get_object()
        serializer = self.get_serializer(step, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": _("Preparation step updated successfully"),
                "preparation_step": serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Preparation Steps'],
        operation_description=_("Partially update a preparation step"),
        request_body=NestedPreparationStepSerializer,
        responses={200: NestedPreparationStepSerializer()}
    )
    def partial_update(self, request, *args, **kwargs):
        step = self.get_object()
        serializer = self.get_serializer(step, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": _("Preparation step updated successfully"),
                "preparation_step": serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Preparation Steps'],
        operation_description=_("Delete a preparation step"),
        responses={204: "No Content"}
    )
    def destroy(self, request, *args, **kwargs):
        step = self.get_object()
        step.delete()
        return Response({"message": _("Preparation step deleted successfully")}, status=status.HTTP_204_NO_CONTENT)

from rest_framework.parsers import JSONParser

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
        responses={201: MealCompletionSerializer()}  # ✅ Added correct response schema
    )
    def post(self, request):
        serializer = CompleteMealSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        session_id = serializer.validated_data.get('session_id')
        meal_id = serializer.validated_data.get('meal_id')

        # Check if the session exists
        session = Session.objects.filter(id=session_id).first()
        if not session:
            return Response({"error": _("Session not found.")}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the meal exists
        meal = Meal.objects.filter(id=meal_id).first()
        if not meal:
            return Response({"error": _("Meal not found.")}, status=status.HTTP_400_BAD_REQUEST)

        # Check user program and subscription status
        user_program = UserProgram.objects.filter(user=request.user, is_active=True).first()
        if not user_program or not user_program.is_subscription_active():
            return Response({"error": _("Your subscription has ended. Please renew.")}, status=status.HTTP_403_FORBIDDEN)

        # Check if meal completion record exists
        meal_completion = MealCompletion.objects.filter(
            session_id=session_id,
            meal_id=meal_id,
            user=request.user
        ).first()

        if not meal_completion:
            return Response({"error": _("Session and Meal combination not found.")}, status=status.HTTP_404_NOT_FOUND)

        # If already completed, return success response
        if meal_completion.is_completed:
            return Response({"message": _("This meal has already been completed.")}, status=status.HTTP_200_OK)

        # Mark the meal as completed
        meal_completion.is_completed = True
        meal_completion.completion_date = now().date()
        meal_completion.save()

        return Response({
            "message": _("Meal completed successfully."),
            "meal_completion": MealCompletionSerializer(meal_completion).data
        }, status=status.HTTP_200_OK)
from rest_framework.parsers import JSONParser

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

        # Check if user has an active subscription
        user_program = UserProgram.objects.filter(user=user, is_active=True).first()
        if not user_program or not user_program.is_subscription_active():
            return Response({"error": _("Your subscription has ended. Please renew.")}, status=status.HTTP_403_FORBIDDEN)

        # Get user sessions for today
        user_sessions = SessionCompletion.objects.filter(user=user, session_date=today).values_list('session_id', flat=True)
        if not user_sessions:
            return Response({"message": _("No sessions found for today.")}, status=status.HTTP_404_NOT_FOUND)

        # Get meals associated with the user's sessions
        meals = Meal.objects.filter(sessions__id__in=user_sessions).distinct()
        if not meals.exists():
            return Response({"message": _("No meals found for today.")}, status=status.HTTP_404_NOT_FOUND)

        # Serialize meals
        serializer = MealDetailSerializer(meals, many=True, context={"language": getattr(user, 'language', 'en')})
        return Response({"meals": serializer.data}, status=status.HTTP_200_OK)


from rest_framework.parsers import JSONParser


class MealDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Retrieve detailed information about a specific meal."),
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
            200: openapi.Response(
                description="Meal details retrieved successfully.",
                examples={
                    "application/json": {
                        "id": 1,
                        "food_name": "Grilled Chicken",
                        "calories": 500,
                        "meal_type": "Lunch",
                        "preparations": [
                            {"name": "Grill chicken", "description": "Grill it for 20 mins."}
                        ]
                    }
                }
            ),
            404: openapi.Response(description="Meal not found.")
        }
    )
    def get(self, request, meal_id):
        # Retrieve meal with preparations
        meal = Meal.objects.prefetch_related('preparations__steps').filter(id=meal_id).first()

        # If meal is not found, return 404 response
        if not meal:
            return Response({"error": _("Meal not found.")}, status=status.HTTP_404_NOT_FOUND)

        # Serialize meal details
        serializer = MealDetailSerializer(meal, context={"language": getattr(request.user, 'language', 'en')})
        return Response(serializer.data, status=status.HTTP_200_OK)

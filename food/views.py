from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework.views import APIView
from users_app.models import Preparation, Meal, MealCompletion, SessionCompletion, Session, PreparationSteps, UserProgram
from rest_framework.parsers import MultiPartParser, FormParser
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

# ----- Define a manual schema for Meal creation -----
manual_meal_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "food_name": openapi.Schema(type=openapi.TYPE_STRING, description="Food name"),
        "preparation_time": openapi.Schema(type=openapi.TYPE_INTEGER, description="Preparation time in minutes"),
        "calories": openapi.Schema(type=openapi.TYPE_NUMBER, description="Calories"),
        "water_content": openapi.Schema(type=openapi.TYPE_NUMBER, description="Water content"),
        "food_photo": openapi.Schema(type=openapi.TYPE_STRING, description="URL of food photo"),
        "description": openapi.Schema(type=openapi.TYPE_STRING, description="Description of the meal"),
        "meal_type": openapi.Schema(type=openapi.TYPE_STRING, description="Meal type (e.g., breakfast, lunch, dinner)"),
        "preparations": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "name": openapi.Schema(type=openapi.TYPE_STRING, description="Preparation name"),
                    "description": openapi.Schema(type=openapi.TYPE_STRING, description="Preparation description"),
                    "preparation_time": openapi.Schema(type=openapi.TYPE_INTEGER, description="Preparation time in minutes"),
                    "calories": openapi.Schema(type=openapi.TYPE_NUMBER, description="Calories for preparation"),
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
                            required=["title", "text"]
                        ),
                        description="Preparation steps"
                    )
                },
                required=["name", "preparation_time"],
                description="A nested preparation object"
            ),
            description="List of nested preparations"
        )
    },
    required=["food_name", "preparation_time", "calories", "meal_type"],
    description="Payload for creating a new meal with nested preparations."
)

# ----- Define a manual schema for Preparation creation -----
manual_preparation_schema = openapi.Schema(
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
)

class MealViewSet(viewsets.ModelViewSet):
    queryset = Meal.objects.all()
    serializer_class = MealNestedSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_context(self):
        language = self.request.query_params.get('lang', 'en')
        return {**super().get_serializer_context(), "language": language}

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Meal.objects.none()
        if not self.request.user.is_authenticated:
            raise PermissionDenied("Authentication is required to view meals.")
        user_program = UserProgram.objects.filter(user=self.request.user, is_active=True).first()
        if not user_program:
            return Meal.objects.none()
        if not user_program.is_subscription_active():
            return Meal.objects.none()
        if not self.request.user.is_staff:
            from users_app.models import SessionCompletion
            sessions = SessionCompletion.objects.filter(user=self.request.user).values_list('session_id', flat=True)
            return Meal.objects.filter(sessions__id__in=sessions).distinct()
        return Meal.objects.all()

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("List all meals for the authenticated user"),
        responses={200: MealNestedSerializer(many=True)},
        query_serializer=EmptyQuerySerializer()
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({"meals": serializer.data})

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Retrieve a specific meal"),
        responses={200: MealNestedSerializer()},
        query_serializer=EmptyQuerySerializer()
    )
    def retrieve(self, request, pk=None):
        meal = self.get_object()
        serializer = self.get_serializer(meal)
        return Response({"meal": serializer.data})

    @swagger_auto_schema(
        tags=['Meals'],
        operation_description=_("Create a new meal with nested preparations"),
        request_body=manual_meal_schema,
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


class MealCompletionViewSet(viewsets.ModelViewSet):
    queryset = MealCompletion.objects.all()
    serializer_class = MealCompletionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return MealCompletion.objects.none()
        return MealCompletion.objects.filter(user=self.request.user)

    def get_serializer_context(self):
        language = self.request.query_params.get('lang', 'en')
        return {**super().get_serializer_context(), "language": language}

    @swagger_auto_schema(
        tags=['Meal Completions'],
        operation_description="List all meal completions for the authenticated user",
        responses={200: MealCompletionSerializer(many=True)},
        query_serializer=EmptyQuerySerializer()
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"meal_completions": serializer.data})

    @swagger_auto_schema(
        tags=['Meal Completions'],
        operation_description="Retrieve a specific meal completion",
        responses={200: MealCompletionSerializer()}
    )
    def retrieve(self, request, pk=None):
        meal_completion = self.get_object()
        serializer = self.get_serializer(meal_completion)
        return Response({"meal_completion": serializer.data})

    @swagger_auto_schema(
        tags=['Meal Completions'],
        operation_description="Create a new meal completion",
        request_body=CompleteMealSerializer,
        responses={201: MealCompletionSerializer()}
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            user_program = UserProgram.objects.filter(user=user, is_active=True).first()
            if not user_program or not user_program.is_subscription_active():
                return Response({"error": "Your subscription has ended. Please renew."}, status=status.HTTP_403_FORBIDDEN)
            session = serializer.validated_data.get('session')
            meal = serializer.validated_data.get('meal')
            if not Session.objects.filter(id=session.id).exists():
                return Response({"error": "Invalid session ID."}, status=status.HTTP_400_BAD_REQUEST)
            if not Meal.objects.filter(id=meal.id).exists():
                return Response({"error": "Invalid meal ID."}, status=status.HTTP_400_BAD_REQUEST)
            meal_completion = serializer.save(user=user)
            return Response({
                "message": "Meal completion recorded successfully",
                "meal_completion": MealCompletionSerializer(meal_completion, context={"language": request.user.language}).data,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Meal Completions'],
        operation_description="Update meal completion status by ID",
        request_body=MealCompletionSerializer,
        responses={200: MealCompletionSerializer()}
    )
    def update(self, request, pk=None, *args, **kwargs):
        meal_completion = self.get_object()
        serializer = self.get_serializer(meal_completion, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Meal completion updated successfully", "meal_completion": serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Meal Completions'],
        operation_description="Partially update a meal completion record",
        request_body=MealCompletionSerializer,
        responses={200: MealCompletionSerializer()}
    )
    def partial_update(self, request, pk=None, *args, **kwargs):
        meal_completion = self.get_object()
        serializer = self.get_serializer(meal_completion, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Meal completion record partially updated successfully", "meal_completion": serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Meal Completions'],
        operation_description="Delete a meal completion record",
        responses={204: "No Content"}
    )
    def destroy(self, request, pk=None, *args, **kwargs):
        meal_completion = self.get_object()
        meal_completion.delete()
        return Response({"message": "Meal completion record deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


class PreparationViewSet(viewsets.ModelViewSet):
    queryset = Preparation.objects.all()
    serializer_class = NestedPreparationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        meal_id = self.request.query_params.get('meal_id')
        if meal_id:
            return self.queryset.filter(meal_id=meal_id)
        return self.queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['language'] = getattr(self.request.user, 'language', 'en')
        return context

    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description="List all preparations.",
        responses={200: NestedPreparationSerializer(many=True)},
        query_serializer=EmptyQuerySerializer()
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description="Retrieve a specific preparation by ID.",
        responses={200: NestedPreparationSerializer()}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description="Create a new preparation with automatic translation.",
        request_body=manual_preparation_schema,
        responses={201: NestedPreparationSerializer()}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description="Update an existing preparation completely.",
        request_body=NestedPreparationSerializer,
        responses={200: NestedPreparationSerializer()}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description="Partially update a preparation.",
        request_body=NestedPreparationSerializer,
        responses={200: NestedPreparationSerializer()}
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description="Delete a preparation by ID.",
        responses={204: "No Content"}
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description="Filter preparations by meal ID.",
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
        preparations = self.get_queryset().filter(meal_id=meal_id)
        serializer = self.get_serializer(preparations, many=True)
        return Response({"preparations": serializer.data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description="Translate preparation fields into multiple languages if missing.",
        responses={
            200: openapi.Response(
                description="Fields translated successfully.",
                examples={"application/json": {"message": "Fields translated successfully."}}
            ),
            404: "Not Found"
        }
    )
    @action(detail=True, methods=['post'], url_path='translate')
    def translate_fields(self, request, pk=None):
        preparation = self.get_object()
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


class PreparationStepViewSet(viewsets.ModelViewSet):
    queryset = PreparationSteps.objects.all()
    serializer_class = NestedPreparationStepSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        preparation_id = self.request.query_params.get('preparation_id')
        if preparation_id:
            return self.queryset.filter(preparation_id=preparation_id)
        return self.queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['language'] = getattr(self.request.user, 'language', 'en')
        return context

    @swagger_auto_schema(
        tags=['Preparation Steps'],
        operation_description="List all preparation steps or filter by preparation_id",
        manual_parameters=[
            openapi.Parameter(
                'preparation_id',
                openapi.IN_QUERY,
                description="Filter preparation steps by preparation ID",
                type=openapi.TYPE_INTEGER
            )
        ],
        responses={200: NestedPreparationStepSerializer(many=True)},
        query_serializer=EmptyQuerySerializer()
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Preparation Steps'],
        operation_description="Retrieve a specific preparation step by ID",
        responses={200: NestedPreparationStepSerializer()}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Preparation Steps'],
        operation_description="Create a new preparation step",
        request_body=NestedPreparationStepSerializer,
        responses={201: NestedPreparationStepSerializer()}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Preparation Steps'],
        operation_description="Update a preparation step",
        request_body=NestedPreparationStepSerializer,
        responses={200: NestedPreparationStepSerializer()}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Preparation Steps'],
        operation_description="Partially update a preparation step",
        request_body=NestedPreparationStepSerializer,
        responses={200: NestedPreparationStepSerializer()}
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        tags=['Preparation Steps'],
        operation_description="Delete a preparation step",
        responses={204: "No Content"}
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class CompleteMealView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=CompleteMealSerializer,
        responses={
            200: "Meal completed successfully.",
            404: "Session and Meal combination not found."
        }
    )
    def post(self, request):
        serializer = CompleteMealSerializer(data=request.data)
        if serializer.is_valid():
            session_id = serializer.validated_data.get('session_id')
            meal_id = serializer.validated_data.get('meal_id')
            user_program = UserProgram.objects.filter(user=request.user, is_active=True).first()
            if not user_program or not user_program.is_subscription_active():
                return Response({"error": _("Your subscription has ended. Please renew.")}, status=403)
            meal_completion = MealCompletion.objects.filter(
                session_id=session_id,
                meal_id=meal_id,
                user=request.user
            ).first()
            if not meal_completion:
                return Response({"error": _("Session and Meal combination not found.")}, status=404)
            if meal_completion.is_completed:
                return Response({"message": _("This meal has already been completed.")}, status=200)
            meal_completion.is_completed = True
            meal_completion.completion_date = now().date()
            meal_completion.save()
            return Response({"message": _("Meal completed successfully.")}, status=200)
        return Response(serializer.errors, status=400)


class UserDailyMealsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = localdate()
        user = request.user
        user_program = UserProgram.objects.filter(user=user, is_active=True).first()
        if not user_program or not user_program.is_subscription_active():
            return Response({"error": _("Your subscription has ended. Please renew.")}, status=403)
        user_sessions = SessionCompletion.objects.filter(user=user, session_date=today).values_list('session_id', flat=True)
        meals = Meal.objects.filter(sessions__id__in=user_sessions).distinct()
        if not meals.exists():
            return Response({"message": _("No meals found for today.")}, status=404)
        serializer = MealDetailSerializer(meals, many=True, context={"language": getattr(user, 'language', 'en')})
        return Response({"meals": serializer.data}, status=200)


class MealDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, meal_id):
        meal = Meal.objects.prefetch_related('preparations', 'preparations__steps').filter(id=meal_id).first()
        if not meal:
            return Response({"error": _("Meal not found.")}, status=404)
        serializer = MealDetailSerializer(meal, context={"language": getattr(request.user, 'language', 'en')})
        return Response(serializer.data, status=200)

from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework.views import APIView
from django.utils.timezone import now
from users_app.models import Preparation, Meal, MealCompletion, SessionCompletion, Session, PreparationSteps
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils.translation import gettext_lazy as _
from googletrans import Translator
from food.serializers import (
    MealSerializer,
    MealCompletionSerializer,
    PreparationSerializer,
    CompleteMealSerializer,
    MealDetailSerializer
)
from rest_framework.exceptions import PermissionDenied
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext as _
from food.serializers import PreparationStepSerializer
from users_app.models import PreparationSteps
from drf_yasg import openapi
from django.utils.timezone import localdate
from .serializers import MealSerializer


translator = Translator()


def translate_text(text, target_language):
    try:
        translation = translator.translate(text, dest=target_language)
        return translation.text
    except Exception as e:
        # If there's an error, return the original text
        print(f"Translation error: {e}")
        return text


class MealViewSet(viewsets.ModelViewSet):
    queryset = Meal.objects.all()
    serializer_class = MealSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_context(self):
        language = self.request.query_params.get('lang', 'en')
        return {**super().get_serializer_context(), "language": language}

    def get_queryset(self):
        # Swagger schema generation uchun autentifikatsiya tekshirishni o'tkazib yuborish
        if getattr(self, 'swagger_fake_view', False):
            return Meal.objects.none()

        # Foydalanuvchi autentifikatsiyadan o‘tsa
        if not self.request.user.is_authenticated:
            raise PermissionDenied("Authentication is required to view meals.")

        # Foydalanuvchi administrator bo'lmagan holatda faqat o'ziga tegishli meallarni ko'rsatamiz
        if not self.request.user.is_staff:
            sessions = SessionCompletion.objects.filter(user=self.request.user).values_list('session_id', flat=True)
            return Meal.objects.filter(sessions__id__in=sessions).distinct()

        # Agar foydalanuvchi administrator bo'lsa, barcha meallarni ko'rsatish
        return Meal.objects.all()

    @swagger_auto_schema(tags=['Meals'], operation_description=_("List all meals for the authenticated user"))
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({"meals": serializer.data})

    @swagger_auto_schema(tags=['Meals'], operation_description=_("Retrieve a specific meal"))
    def retrieve(self, request, pk=None):
        meal = self.get_object()
        serializer = self.get_serializer(meal)
        return Response({"meal": serializer.data})

    @swagger_auto_schema(tags=['Meals'], operation_description=_("Create a new meal with optional photo upload"))
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Meal created successfully", "meal": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=['Meals'], operation_description=_("Update a meal by ID"))
    def update(self, request, pk=None, *args, **kwargs):
        meal = self.get_object()
        serializer = self.get_serializer(meal, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Meal updated successfully", "meal": serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=['Meals'], operation_description=_("Partially update a meal by ID"))
    def partial_update(self, request, pk=None, *args, **kwargs):
        meal = self.get_object()
        serializer = self.get_serializer(meal, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Meal partially updated successfully", "meal": serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=['Meals'], operation_description=_("Delete a meal"))
    def destroy(self, request, pk=None, *args, **kwargs):
        meal = self.get_object()
        meal.delete()
        return Response({"message": "Meal deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


class MealCompletionViewSet(viewsets.ModelViewSet):
    queryset = MealCompletion.objects.all()
    serializer_class = MealCompletionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # If the view is accessed by Swagger or the user is not authenticated, return an empty queryset
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return MealCompletion.objects.none()
        return MealCompletion.objects.filter(user=self.request.user)

    def get_serializer_context(self):
        # Use 'lang' query parameter to determine language, with 'en' as the default
        language = self.request.query_params.get('lang', 'en')
        return {**super().get_serializer_context(), "language": language}

    @swagger_auto_schema(tags=['Meal Completions'],
                         operation_description=_("List all meal completions for the authenticated user"))
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"meal_completions": serializer.data})

    @swagger_auto_schema(tags=['Meal Completions'], operation_description=_("Retrieve a specific meal completion"))
    def retrieve(self, request, pk=None):
        meal_completion = self.get_object()
        serializer = self.get_serializer(meal_completion)
        return Response({"meal_completion": serializer.data})

    @swagger_auto_schema(tags=['Meal Completions'], operation_description=_("Create a new meal completion"))
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            session = serializer.validated_data.get('session')  # Extract session
            meal = serializer.validated_data.get('meal')  # Extract meal
            user = request.user

            # Ensure the session and meal are valid
            if not Session.objects.filter(id=session.id).exists():
                return Response({"error": _("Invalid session ID.")}, status=status.HTTP_400_BAD_REQUEST)

            if not Meal.objects.filter(id=meal.id).exists():
                return Response({"error": _("Invalid meal ID.")}, status=status.HTTP_400_BAD_REQUEST)

            # Save the meal completion
            meal_completion = serializer.save(user=user)
            return Response(
                {
                    "message": _("Meal completion recorded successfully"),
                    "meal_completion": MealCompletionSerializer(meal_completion, context={"language": request.user.language}).data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=['Meal Completions'], operation_description=_("Update meal completion status by ID"))
    def update(self, request, pk=None, *args, **kwargs):
        meal_completion = self.get_object()
        serializer = self.get_serializer(meal_completion, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Meal completion updated successfully", "meal_completion": serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=['Meal Completions'], operation_description=_("Partially update a meal completion record"))
    def partial_update(self, request, pk=None, *args, **kwargs):
        meal_completion = self.get_object()
        serializer = self.get_serializer(meal_completion, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Meal completion record partially updated successfully", "meal_completion": serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def schedule_reminder(self, meal_completion):
        """
        Schedules a reminder for a meal based on the user's preferred reminder time offset.
        """
        user_reminder_offset = getattr(self.request.user, 'reminder_time', None)
        if meal_completion.meal and meal_completion.meal.scheduled_time and user_reminder_offset:
            meal_time = meal_completion.meal.scheduled_time
            reminder_time = datetime.combine(timezone.now().date(), meal_time) - timedelta(
                minutes=user_reminder_offset.minute)

            # Placeholder for scheduling logic
            # Implement your logic to actually schedule the reminder (e.g., using Celery or Django signals)
            print(f"Reminder scheduled at {reminder_time} for meal at {meal_time}")

    @swagger_auto_schema(tags=['Meal Completions'], operation_description=_("Delete a meal completion record"))
    def destroy(self, request, pk=None, *args, **kwargs):
        meal_completion = self.get_object()
        meal_completion.delete()
        return Response({"message": "Meal completion record deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


class PreparationViewSet(viewsets.ModelViewSet):
    queryset = Preparation.objects.all()
    serializer_class = PreparationSerializer
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

    # Swagger for List Method
    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description="List all preparations.",
        responses={200: PreparationSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    # Swagger for Retrieve Method
    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description="Retrieve a specific preparation by ID.",
        responses={200: PreparationSerializer()}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    # Swagger for Create Method
    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description="Create a new preparation with automatic translation.",
        request_body=PreparationSerializer,
        responses={201: PreparationSerializer()}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    # Swagger for Update Method (PUT)
    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description="Update an existing preparation completely.",
        request_body=PreparationSerializer,
        responses={200: PreparationSerializer()}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    # Swagger for Partial Update Method (PATCH)
    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description="Partially update a preparation.",
        request_body=PreparationSerializer,
        responses={200: PreparationSerializer()}
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    # Swagger for Delete Method
    @swagger_auto_schema(
        tags=['Preparations'],
        operation_description="Delete a preparation by ID.",
        responses={204: "No Content"}
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    # Custom Endpoint: Filter Preparations by Meal ID
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
        responses={200: PreparationSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='by-meal')
    def get_by_meal(self, request):
        meal_id = request.query_params.get('meal_id')
        if not meal_id:
            return Response(
                {"error": _("meal_id is required.")},
                status=status.HTTP_400_BAD_REQUEST
            )

        preparations = self.get_queryset().filter(meal_id=meal_id)
        serializer = self.get_serializer(preparations, many=True)
        return Response({"preparations": serializer.data}, status=status.HTTP_200_OK)

    # Custom Endpoint: Translate Fields
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

        # Translate fields if they are missing
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
    serializer_class = PreparationStepSerializer
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

    # List method uchun swagger_auto_schema
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
        responses={200: PreparationStepSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    # Retrieve method uchun swagger_auto_schema
    @swagger_auto_schema(
        tags=['Preparation Steps'],
        operation_description="Retrieve a specific preparation step by ID",
        responses={200: PreparationStepSerializer()}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    # Create method uchun swagger_auto_schema
    @swagger_auto_schema(
        tags=['Preparation Steps'],
        operation_description="Create a new preparation step",
        request_body=PreparationStepSerializer,
        responses={201: PreparationStepSerializer()}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    # Update method uchun swagger_auto_schema
    @swagger_auto_schema(
        tags=['Preparation Steps'],
        operation_description="Update a preparation step",
        request_body=PreparationStepSerializer,
        responses={200: PreparationStepSerializer()}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    # Partial Update method uchun swagger_auto_schema
    @swagger_auto_schema(
        tags=['Preparation Steps'],
        operation_description="Partially update a preparation step",
        request_body=PreparationStepSerializer,
        responses={200: PreparationStepSerializer()}
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    # Delete method uchun swagger_auto_schema
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
            200: "Taom muvaffaqiyatli bajarildi.",
            404: "Session va Meal kombinatsiyasi topilmadi."
        }
    )
    def post(self, request):
        serializer = CompleteMealSerializer(data=request.data)
        if serializer.is_valid():
            session_id = serializer.validated_data.get('session_id')
            meal_id = serializer.validated_data.get('meal_id')

            # MealCompletion obyektini topish
            meal_completion = MealCompletion.objects.filter(
                session_id=session_id,
                meal_id=meal_id,
                user=request.user
            ).first()

            if not meal_completion:
                return Response({"error": "Session va Meal kombinatsiyasi topilmadi."}, status=404)

            if meal_completion.is_completed:
                return Response({"message": "Ushbu taom allaqachon bajarilgan."}, status=200)

            # MealCompletionni bajarilgan deb belgilash
            meal_completion.is_completed = True
            meal_completion.completion_date = now().date()
            meal_completion.save()

            return Response({"message": "Taom muvaffaqiyatli bajarildi."}, status=200)

        return Response(serializer.errors, status=400)


class UserDailyMealsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = localdate()  # Bugungi sana olish
        user = request.user

        # Bugungi sessiyalarni olish
        user_sessions = SessionCompletion.objects.filter(
            user=user,
            session_date=today
        ).values_list('session_id', flat=True)  # Faqat session_id larni olish

        # Ushbu sessiyalarga bog'langan Meal obyektlarini olish
        meals = Meal.objects.filter(
            sessions__id__in=user_sessions
        ).distinct()  # Takrorlangan ma'lumotlarni oldini olish

        # Ma'lumotlarni serializer orqali chiqarish
        serializer = MealSerializer(meals, many=True, context={"language": getattr(request.user, 'language', 'en')})

        # Bo'sh ma'lumotlar uchun xabar
        if not meals.exists():
            return Response(
                {"message": "Bugungi kunga taomlar topilmadi."},
                status=404
            )

        return Response({"meals": serializer.data}, status=200)


class MealDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, meal_id):
        meal = Meal.objects.prefetch_related('preparations', 'preparations__steps').filter(id=meal_id).first()

        if not meal:
            return Response(
                {"error": _("Meal not found.")},
                status=404
            )

        serializer = MealDetailSerializer(meal, context={"language": request.user.language})

        return Response(serializer.data, status=200)





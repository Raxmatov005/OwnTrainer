from django.shortcuts import render
from django.utils.timezone import now, timedelta
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from django.db.models import Count, Sum, Q
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from users_app.models import User, UserProgram, SessionCompletion, Session, Meal, Exercise
from food.serializers import MealListSerializer
from exercise.serializers import ExerciseBlockListSerializer
from .pagination import AdminPageNumberPagination
from users_app.serializers import UserSerializer
from rest_framework.permissions import AllowAny  # ✅ Add this line
from rest_framework.generics import GenericAPIView  # ✅ Add this import
from itertools import chain

from admin_app.serializers import AdminLoginSerializer  # ✅ Ensure this is correctly imported

from rest_framework_simplejwt.tokens import RefreshToken  # ✅ Import JWT token generator
from admin_app.serializers import AdminLoginSerializer  # Ensure this is correctly imported

### **🔹 Admin Statistics View (Dashboard)**
from django.utils import timezone


class AdminUserStatisticsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        today = timezone.now().date()
        seven_days_ago = today - timedelta(days=7)
        one_month_ago = today - timedelta(days=30)

        # Top section statistics
        total_users = User.objects.count()
        users_today = User.objects.filter(date_joined__date=today).count()
        premium_users = User.objects.filter(is_premium=True).count()
        non_premium_users = User.objects.filter(is_premium=False).count()
        total_exercises = Exercise.objects.count()
        total_meals = Meal.objects.count()
        registered_last_7_days = User.objects.filter(date_joined__gte=seven_days_ago).count()
        registered_last_month = User.objects.filter(date_joined__gte=one_month_ago).count()

        # Replace is_paid filters with actual related field lookups
        active_subscriptions = UserProgram.objects.filter(
            is_active=True,
            user__subscriptions__is_active=True,
            user__subscriptions__end_date__gte=today
        ).distinct().count()

        inactive_subscriptions = UserProgram.objects.filter(
            is_active=True
        ).exclude(
            user__subscriptions__is_active=True,
            user__subscriptions__end_date__gte=today
        ).distinct().count()

        total_income_qs = UserProgram.objects.filter(
            user__subscriptions__is_active=True,
            user__subscriptions__end_date__gte=today
        ).aggregate(total_income=Sum('amount'))
        total_income = total_income_qs["total_income"] if total_income_qs["total_income"] is not None else 0

        top_section_data = {
            "users_today": users_today,
            "total_users": total_users,
            "premium_users": premium_users,
            "non_premium_users": non_premium_users,
            "total_exercises": total_exercises,
            "total_meals": total_meals,
            "registered_last_7_days": registered_last_7_days,
            "registered_last_month": registered_last_month,
            "active_subscriptions": active_subscriptions,
            "inactive_subscriptions": inactive_subscriptions,
            "total_income": total_income,
        }

        # Bottom section: Grouped by country
        countries_data = (
            User.objects.values("country")
            .annotate(
                total_users=Count("id"),
                subscribers=Count("id", filter=Q(is_premium=True)),
                non_subscribers=Count("id", filter=Q(is_premium=False)),
                active_users=Count("id", filter=Q(is_active=True)),
                inactive_users=Count("id", filter=Q(is_active=False)),
                active_subscriptions=Count("user_programs", filter=Q(
                    user_programs__is_active=True,
                    subscriptions__is_active=True,
                    subscriptions__end_date__gte=today
                )),
                inactive_subscriptions=Count("user_programs", filter=~Q(
                    subscriptions__is_active=True,
                    subscriptions__end_date__gte=today
                )),
                income=Sum("user_programs__amount", filter=Q(
                    user_programs__is_active=True,
                    subscriptions__is_active=True,
                    subscriptions__end_date__gte=today
                )),
            )
        )

        bottom_section_data = [
            {
                "country": country["country"],
                "total_users": country["total_users"],
                "subscribers": country["subscribers"],
                "non_subscribers": country["non_subscribers"],
                "active_users": country["active_users"],
                "inactive_users": country["inactive_users"],
                "active_subscriptions": country["active_subscriptions"],
                "inactive_subscriptions": country["inactive_subscriptions"],
                "income": country["income"] or 0,
            }
            for country in countries_data
        ]

        return Response(
            {
                "top_section": top_section_data,
                "bottom_section": bottom_section_data,
            },
            status=200,
        )


### **🔹 Admin User Management (Paginated User List)**
class AdminGetAllUsersView(ListAPIView):
    permission_classes = [IsAdminUser]
    queryset = User.objects.all()
    pagination_class = AdminPageNumberPagination
    serializer_class = UserSerializer  # 🔹 You need a `UserSerializer`



class AdminLoginView(GenericAPIView):  # ✅ Change from APIView to GenericAPIView
    permission_classes = [AllowAny]
    serializer_class = AdminLoginSerializer  # ✅ Explicitly define the serializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)  # ✅ Use DRF's serializer handling
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email_or_phone = serializer.validated_data["email_or_phone"]
        password = serializer.validated_data["password"]

        # ✅ Check if user exists using either email or phone
        try:
            user = User.objects.get(email_or_phone=email_or_phone)
        except User.DoesNotExist:
            return Response({"error": "Invalid credentials"}, status=400)

        if not user.check_password(password):
            return Response({"error": "Invalid credentials"}, status=400)

        if not user.is_staff:
            return Response({"error": "Access denied. Only admins can log in."}, status=403)

        # ✅ Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        return Response({
            "access": access_token,
            "refresh": str(refresh),
            "message": "Admin login successful!"
        }, status=200)



### **🔹 Admin Content Management (Paginated)**
class AdminContentViewSet(viewsets.ViewSet):
    """
    This viewset provides separate endpoints to list Exercises (actually blocks),
    list Meals, or list all content, each with pagination.
    """
    permission_classes = [IsAdminUser]
    pagination_class = AdminPageNumberPagination

    def get_queryset(self, content_type):
        if content_type == "blocks":   # or "exercises" if you prefer the name
            return ExerciseBlock.objects.all()
        elif content_type == "meals":
            return Meal.objects.all()
        elif content_type == "all":
            # Combine both into a single Python list
            blocks = list(ExerciseBlock.objects.all())
            meals = list(Meal.objects.all())
            return list(chain(blocks, meals))  # or blocks + meals
        return ExerciseBlock.objects.none()

    @swagger_auto_schema(
        operation_description="List all exercise blocks (paginated).",
        responses={200: openapi.Response(description="Success")}
    )
    @action(detail=False, methods=['get'], url_path='exercises')
    def list_exercises(self, request):
        """
        If your code calls them 'blocks' but the URL is 'exercises', you can rename accordingly.
        We'll just show how to list them using a list serializer.
        """
        queryset = self.get_queryset("blocks")
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request, view=self)
        serializer = ExerciseBlockListSerializer(paginated_queryset, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    @swagger_auto_schema(
        operation_description="List all meals (paginated).",
        responses={200: openapi.Response(description="Success")}
    )
    @action(detail=False, methods=['get'], url_path='meals')
    def list_meals(self, request):
        queryset = self.get_queryset("meals")
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request, view=self)
        serializer = MealListSerializer(paginated_queryset, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    @swagger_auto_schema(
        operation_description="List both exercise blocks and meals (paginated separately).",
        responses={200: openapi.Response(description="Success")}
    )
    @action(detail=False, methods=['get'], url_path='all')
    def list_all_content(self, request):
        """
        We'll paginate them separately if you want.
        Or you can combine them in a single list,
        but then you'll need a single universal serializer or custom logic.
        """
        # Example: separate pagination for blocks vs. meals
        blocks = ExerciseBlock.objects.all()
        meals = Meal.objects.all()

        paginator = self.pagination_class()

        paginated_blocks = paginator.paginate_queryset(blocks, request, view=self)
        blocks_data = ExerciseBlockListSerializer(paginated_blocks, many=True, context={'request': request}).data

        # Careful: calling paginate_queryset again for 'meals'
        # might reuse the same pagination state.
        # Usually you'd do separate endpoints or custom logic.
        # We'll just do a custom merge approach for demonstration.

        paginated_meals = paginator.paginate_queryset(meals, request, view=self)
        meals_data = MealListSerializer(paginated_meals, many=True, context={'request': request}).data

        # Combine them in one response if desired
        response_data = {
            "blocks": blocks_data,
            "meals": meals_data
        }
        return Response(response_data, status=status.HTTP_200_OK)
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
from food.serializers import MealNestedSerializer
from exercise.serializers import NestedExerciseSerializer
from .pagination import AdminPageNumberPagination
from users_app.serializers import UserSerializer
from rest_framework.permissions import AllowAny  # ✅ Add this line
from rest_framework.generics import GenericAPIView  # ✅ Add this import


from admin_app.serializers import AdminLoginSerializer  # ✅ Ensure this is correctly imported

from rest_framework_simplejwt.tokens import RefreshToken  # ✅ Import JWT token generator
from admin_app.serializers import AdminLoginSerializer  # Ensure this is correctly imported

### **🔹 Admin Statistics View (Dashboard)**
class AdminUserStatisticsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        today = now().date()
        seven_days_ago = today - timedelta(days=7)
        one_month_ago = today - timedelta(days=30)

        ### **TOP SECTION - Overall Statistics (3 UI Cells)**
        total_users = User.objects.count()
        users_today = User.objects.filter(date_joined__date=today).count()
        premium_users = User.objects.filter(is_premium=True).count()
        non_premium_users = User.objects.filter(is_premium=False).count()

        total_exercises = Exercise.objects.count()
        total_meals = Meal.objects.count()

        registered_last_7_days = User.objects.filter(date_joined__gte=seven_days_ago).count()
        registered_last_month = User.objects.filter(date_joined__gte=one_month_ago).count()

        active_subscriptions = UserProgram.objects.filter(is_paid=True, is_active=True).count()
        inactive_subscriptions = UserProgram.objects.filter(is_paid=False).count()

        total_income = UserProgram.objects.filter(is_paid=True).aggregate(total_income=Sum('amount'))
        total_income = total_income["total_income"] if total_income["total_income"] is not None else 0

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

        ### **BOTTOM SECTION - Grouped by Country**
        countries_data = (
            User.objects.values("country")
            .annotate(
                total_users=Count("id"),
                subscribers=Count("id", filter=Q(is_premium=True)),
                non_subscribers=Count("id", filter=Q(is_premium=False)),
                active_users=Count("id", filter=Q(is_active=True)),
                inactive_users=Count("id", filter=Q(is_active=False)),
                active_subscriptions=Count("user_programs", filter=Q(user_programs__is_paid=True, user_programs__is_active=True)),
                inactive_subscriptions=Count("user_programs", filter=Q(user_programs__is_paid=False)),
                income=Sum("user_programs__amount", filter=Q(user_programs__is_paid=True)),
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
    permission_classes = [IsAdminUser]
    pagination_class = AdminPageNumberPagination

    def get_queryset(self, content_type):
        if content_type == "exercises":
            return Exercise.objects.all()
        elif content_type == "meals":
            return Meal.objects.all()
        return Exercise.objects.none()

    @action(detail=False, methods=['get'], url_path='exercises')
    def list_exercises(self, request):
        queryset = self.get_queryset("exercises")
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = NestedExerciseSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'], url_path='meals')
    def list_meals(self, request):
        queryset = self.get_queryset("meals")
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = MealNestedSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'], url_path='all')
    def list_all_content(self, request):
        queryset_exercises = Exercise.objects.all()
        queryset_meals = Meal.objects.all()
        paginator = self.pagination_class()

        paginated_exercises = paginator.paginate_queryset(queryset_exercises, request)
        paginated_meals = paginator.paginate_queryset(queryset_meals, request)

        response_data = {
            "exercises": NestedExerciseSerializer(paginated_exercises, many=True).data,
            "meals": MealNestedSerializer(paginated_meals, many=True).data
        }

        return paginator.get_paginated_response(response_data)

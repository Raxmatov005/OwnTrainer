from django.shortcuts import render

# Create your views here.
from django.utils.timezone import now, timedelta
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from users_app.models import User
from django.db.models import Q
from rest_framework import status  # status import qilingan



class AdminUserStatisticsView(APIView):
    # permission_classes = [IsAdminUser]  # Faqat adminlar uchun

    def get(self, request):
        # Umumiy foydalanuvchilar soni
        total_users = User.objects.count()

        # Premium foydalanuvchilar soni
        premium_users = User.objects.filter(is_premium=True).count()
        non_premium_users = User.objects.filter(is_premium=False).count()

        # Faol foydalanuvchilar (is_active=True)
        active_users = User.objects.filter(is_active=True).count()
        inactive_users = User.objects.filter(is_active=False).count()

        # Oxirgi 7 kun ichida ro'yxatdan o'tgan foydalanuvchilar
        seven_days_ago = now() - timedelta(days=7)
        registered_last_7_days = User.objects.filter(date_joined__gte=seven_days_ago).count()

        # Oxirgi 1 oyda ro'yxatdan o'tgan foydalanuvchilar
        one_month_ago = now() - timedelta(days=30)
        registered_last_month = User.objects.filter(date_joined__gte=one_month_ago).count()

        # Oxirgi 7 kun ichida tizimdan chiqqan foydalanuvchilar
        logged_out_last_7_days = User.objects.filter(
            Q(is_active=False) & Q(last_login__gte=seven_days_ago)
        ).count()

        # Oxirgi 1 oyda tizimdan chiqqan foydalanuvchilar
        logged_out_last_month = User.objects.filter(
            Q(is_active=False) & Q(last_login__gte=one_month_ago)
        ).count()

        # Statistika javobi
        data = {
            "total_users": total_users,
            "premium_users": premium_users,
            "non_premium_users": non_premium_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "registered_last_7_days": registered_last_7_days,
            "registered_last_month": registered_last_month,
            "logged_out_last_7_days": logged_out_last_7_days,
            "logged_out_last_month": logged_out_last_month,
        }

        return Response(data, status=200)



class AdminGetAllUsersView(APIView):
    # permission_classes = [IsAdminUser]  # Faqat adminlar kirishi mumkin

    def get(self, request):
        # Barcha foydalanuvchilarni olish
        users = User.objects.all()
        users_data = [
            {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email_or_phone": user.email_or_phone,
                "gender": user.gender,
                "country": user.country,
                "age": user.age,
                "height": user.height,
                "weight": user.weight,
                "goal": user.goal,
                "level": user.level,
                "is_premium": user.is_premium,
                "language": user.language,
                "is_active": user.is_active,
                "date_joined": user.date_joined,
                "last_login": user.last_login,
            }
            for user in users
        ]

        return Response(users_data, status=status.HTTP_200_OK)  # status ishlatiladi
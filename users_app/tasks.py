from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from celery import shared_task
from .models import Notification
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'register.settings')
django.setup()





@shared_task
def schedule_notification(notification_id):
    try:
        notification = Notification.objects.get(id=notification_id)
        user_email = notification.user.email_or_phone  # Email yoki telefon

        # Emailni tekshirish
        try:
            validate_email(user_email)
        except ValidationError:
            print(f"Invalid email format: {user_email}")
            return  # Noto'g'ri email bo'lsa, hech narsa qilmay chiqib ketish

        # Notificationni foydalanuvchiga yuborish
        send_mail(
            subject="Reminder Notification",
            message=notification.message,
            from_email="sohajon2005@gmail.com",  # Sizning emailingiz
            recipient_list=[user_email],  # To'g'ri email manzil
            fail_silently=False,
        )

        # Notificationni o'qilgan deb belgilash
        notification.is_read = True
        notification.save()

    except Notification.DoesNotExist:
        print(f"Notification with ID {notification_id} does not exist.")

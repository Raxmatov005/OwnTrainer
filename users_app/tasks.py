from celery import shared_task
from .models import Notification
from .notifications import NotificationService
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'register.settings')
django.setup()



@shared_task
def send_scheduled_notification(notification_id):
    try:
        notification = Notification.objects.get(id=notification_id)
        NotificationService.send_push_notification(notification.user, notification.message)
        notification.is_read = True
        notification.save()
    except Notification.DoesNotExist:
        print(f"Notification with ID {notification_id} does not exist.")

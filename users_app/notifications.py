from django.utils import translation
from users_app.models import Notification
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from fcm_django.models import FCMDevice


class NotificationService:
    @staticmethod
    def send_push_notification(user, message):
        if user.device_token:
            device = FCMDevice.objects.create(registration_id=user.device_token, user=user)
            device.send_message(title="Reminder", body=message)
        else:
            print(f"User {user.email_or_phone} does not have a device token.")

    @staticmethod
    def schedule_reminders():
        from django.utils.timezone import now
        notifications = Notification.objects.filter(
            notification_type="reminder",
            is_read=False,
            scheduled_time__lte=now()
        )

        for notification in notifications:
            NotificationService.send_push_notification(notification.user, notification.message)
            notification.is_read = True
            notification.sent_at = now()
            notification.save()

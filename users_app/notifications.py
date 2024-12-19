from django.utils import translation
from users_app.models import Notification
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class NotificationService:
    @staticmethod
    def send_notification(user, message_key, notification_type="general", **kwargs):
        # Set language to user's preferred language
        language = user.language
        translation.activate(language)

        # Translate and format the message
        message = _(message_key).format(**kwargs)

        # Store notification in the database
        notification = Notification.objects.create(
            user=user,
            message=message,
            language=language,
            notification_type=notification_type,
            scheduled_time=user.reminder_time if notification_type == "reminder" else None,
        )

        # Send email notification if enabled
        if user.notification_preferences.get("email", False):
            send_mail(
                subject=_("Notification"),
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email_or_phone]
            )

        # Add other notification channels (e.g., SMS) if required

        translation.deactivate()
        return notification

    @staticmethod
    def schedule_reminders():
        now = timezone.now()
        notifications = Notification.objects.filter(
            notification_type="reminder",
            is_read=False,
            scheduled_time__lte=now.time(),
            sent_at__date__lt=now.date()
        )

        for notification in notifications:
            if notification.user.notification_preferences.get("reminder_enabled", False):
                NotificationService.send_notification(
                    user=notification.user,
                    message_key="Remember to complete your session!",
                    notification_type="reminder"
                )
            # Update the sent time and mark the notification as sent today
            notification.sent_at = now
            notification.save()

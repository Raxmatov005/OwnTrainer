from django.core.management.base import BaseCommand
from users_app.notifications import NotificationService
import logging


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send scheduled reminders to users'

    def handle(self, *args, **options):
        try:
            NotificationService.schedule_reminders()
            self.stdout.write(self.style.SUCCESS('Successfully sent reminders'))
            logger.info('Successfully sent reminders')
        except Exception as e:
            logger.error(f"Failed to send reminders: {e}")
            self.stdout.write(self.style.ERROR('Failed to send reminders'))

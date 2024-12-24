from django.apps import AppConfig
from django.db.models.signals import post_migrate

class UsersAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users_app'

    def ready(self):
        import users_app.signals  # Import signals

from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate
from django.dispatch import receiver

@receiver(post_migrate)
def create_superuser(sender, **kwargs):
    User = get_user_model()
    if not User.objects.filter(is_superuser=True).exists():
        print("Creating default superuser...")
        User.objects.create_superuser(
            email_or_phone="+998999999999",
            password="admin",
            first_name="Admin",  # Provide required defaults explicitly
            last_name="User",
            age=30,
            height=170,
            weight=70,
            goal="General Fitness",
            level="Intermediate",
            photo="default_photo.jpg",
        )
        print("Superuser created successfully!")
    else:
        print("Superuser already exists.")

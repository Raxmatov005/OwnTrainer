from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group, Permission
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from googletrans import Translator
from django.utils import timezone
from django.utils.timezone import now

translator = Translator()


def translate_text(text, target_language):
    try:
        translation = translator.translate(text, dest=target_language)
        return translation.text if translation else text
    except Exception as e:
        print(f"Translation error: {e}")
        return text



def default_notification_preferences():
    return {"email": False, "push_notification": True, "reminder_enabled": True}


class CustomUserManager(BaseUserManager):
    def create_user(self, email_or_phone, password=None, **extra_fields):
        if not email_or_phone:
            raise ValueError("The Email or Phone must be set")

        # Ensure all required fields have valid defaults or raise errors
        extra_fields.setdefault('first_name', 'Admin')
        extra_fields.setdefault('last_name', 'User')
        extra_fields.setdefault('age', 30)  # Default age for admin
        extra_fields.setdefault('height', 170)  # Default height
        extra_fields.setdefault('weight', 70)  # Default weight
        extra_fields.setdefault('goal', 'General Fitness')
        extra_fields.setdefault('level', 'Intermediate')
        extra_fields.setdefault('photo', 'default_photo.jpg')  # Default photo path

        user = self.model(email_or_phone=email_or_phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email_or_phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email_or_phone, password, **extra_fields)



class User(AbstractBaseUser, PermissionsMixin):
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('ru', 'Russian'),
        ('uz', 'Uzbek'),
    ]

    first_name = models.CharField(max_length=30, blank=False, null=False)
    last_name = models.CharField(max_length=30, blank=False, null=False)
    email_or_phone = models.CharField(max_length=255, unique=True, blank=False, null=False)
    phone_or_email_optional = models.CharField(max_length=55, null=True, blank=True)
    password = models.CharField(max_length=128)
    date_joined = models.DateTimeField(default=now, verbose_name="Date Joined")  # Yangi maydon

    gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female')], blank=True, null=True)
    country = models.CharField(max_length=50, blank=True, null=True, choices=[('Uzbekistan', 'Uzbekistan'), ('Russia', 'Russia'), ('Kazakhstan', 'Kazakhstan'), ('Other', 'Other')], default='Other')
    notification_preferences = models.JSONField(default=default_notification_preferences)
    device_token = models.CharField(max_length=255, blank=True, null=True)
    reminder_time = models.TimeField(blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True, validators=[MinValueValidator(16), MaxValueValidator(50)])
    height = models.PositiveIntegerField(blank=True, null=True,
                                         validators=[MinValueValidator(140), MaxValueValidator(220)])
    weight = models.PositiveIntegerField(blank=True, null=True,
                                         validators=[MinValueValidator(30), MaxValueValidator(200)])
    goal = models.CharField(max_length=255, blank=True, null=True)
    level = models.CharField(max_length=50, blank=True, null=True)
    is_premium = models.BooleanField(default=False)
    photo = models.ImageField(upload_to='user_photos/', blank=True, null=True)
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default='en')


    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)

    groups = models.ManyToManyField(Group, related_name="custom_user_groups", blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name="custom_user_permissions", blank=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email_or_phone'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def __str__(self):
        return self.email_or_phone


class UserProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    completed_sessions = models.IntegerField(default=0)
    total_calories_burned = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    calories_gained = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    missed_sessions = models.IntegerField(default=0)
    week_number = models.IntegerField()
    program = models.ForeignKey('Program', on_delete=models.CASCADE)  # Link to the program for tracking


class Program(models.Model):
    frequency_per_week = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(7)])
    total_sessions = models.IntegerField(default=0)  # Number of sessions in the program
    program_goal = models.CharField(max_length=255)
    program_goal_uz = models.CharField(max_length=255, blank=True, null=True)
    program_goal_ru = models.CharField(max_length=255, blank=True, null=True)
    program_goal_en = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.program_goal_uz:
            self.program_goal_uz = translate_text(self.program_goal, 'uz')
        if not self.program_goal_ru:
            self.program_goal_ru = translate_text(self.program_goal, 'ru')
        if not self.program_goal_en:
            self.program_goal_en = translate_text(self.program_goal, 'en')
        super(Program, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.program_goal} "

    def increment_progress(self):
        """Increment the progress by 1, until it reaches total_sessions."""
        if self.progress < self.total_sessions:
            self.progress += 1
            self.save()
        if self.progress == self.total_sessions:
            self.is_active = False
            self.save()


class UserProgram(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_programs", null=True)
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="user_programs", null=True)
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField(null=True, blank=True)
    progress = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    amount = models.IntegerField(blank=True, null=True)
    is_paid = models.BooleanField(default=False)
    payment_method = models.CharField(max_length=255)


    def calculate_progress(self):
        total_sessions = self.program.total_sessions
        completed_sessions = SessionCompletion.objects.filter(
            user=self.user,
            session__program=self.program,
            is_completed=True
        ).count()
        return (completed_sessions / total_sessions) * 100 if total_sessions > 0 else 0

    def __str__(self):
        program_goal = self.program.program_goal if self.program else "No Program"
        return f"{self.user} - {program_goal}"


class WorkoutCategory(models.Model):
    category_name = models.CharField(max_length=255)
    category_name_uz = models.CharField(max_length=255, blank=True, null=True)
    category_name_ru = models.CharField(max_length=255, blank=True, null=True)
    category_name_en = models.CharField(max_length=255, blank=True, null=True)

    description = models.TextField()
    description_uz = models.TextField(blank=True, null=True)
    description_ru = models.TextField(blank=True, null=True)
    description_en = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.category_name_uz:
            self.category_name_uz = translate_text(self.category_name, 'uz')
        if not self.category_name_ru:
            self.category_name_ru = translate_text(self.category_name, 'ru')
        if not self.category_name_en:
            self.category_name_en = translate_text(self.category_name, 'en')

        if not self.description_uz:
            self.description_uz = translate_text(self.description, 'uz')
        if not self.description_ru:
            self.description_ru = translate_text(self.description, 'ru')
        if not self.description_en:
            self.description_en = translate_text(self.description, 'en')

        super(WorkoutCategory, self).save(*args, **kwargs)

    def __str__(self):
        return self.category_name


class Session(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE,related_name="sessions")
    calories_burned = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    session_number = models.IntegerField(null=False)
    session_time = models.TimeField(null=True, blank=True)
    cover_image=models.FileField(upload_to='session/image',blank=True,null=True)

    exercises = models.ManyToManyField('Exercise', related_name='sessions')
    meals = models.ManyToManyField('Meal', related_name='sessions')

    def __str__(self):
        return f"Session on {self.session_number} - {self.program}"


class SessionCompletion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="session_completions")
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="completions")
    is_completed = models.BooleanField(default=False)
    completion_date = models.DateField(null=True, blank=True)
    session_date = models.DateField(null=True, blank=True)  # New field for planned date
    session_number_private = models.IntegerField(null=False)


    class Meta:
        unique_together = ('user', 'session')  # Ensures unique tracking per user-session combination

    def save(self, *args, **kwargs):
        if self.is_completed and not self.completion_date:
            self.completion_date = timezone.now().date()
        super(SessionCompletion, self).save(*args, **kwargs)

    def __str__(self):
        status = "Completed" if self.is_completed else "Pending"
        return f"{self.user.email_or_phone} - {self.session.program.program_goal} ({status})"


class Exercise(models.Model):
    category = models.ForeignKey(WorkoutCategory, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)
    exercise_time = models.DurationField(null=True, blank=True)
    name_uz = models.CharField(max_length=255, blank=True, null=True)
    name_ru = models.CharField(max_length=255, blank=True, null=True)
    name_en = models.CharField(max_length=255, blank=True, null=True)

    description = models.TextField()
    description_uz = models.TextField(blank=True, null=True)
    description_ru = models.TextField(blank=True, null=True)
    description_en = models.TextField(blank=True, null=True)

    difficulty_level = models.CharField(max_length=50)  # E.g., Beginner, Intermediate, Advanced
    target_muscle = models.CharField(max_length=255)
    video_url = models.URLField(blank=True, null=True)
    image = models.ImageField(upload_to='exercise_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.name_uz:
            self.name_uz = translate_text(self.name, 'uz')
        if not self.name_ru:
            self.name_ru = translate_text(self.name, 'ru')
        if not self.name_en:
            self.name_en = translate_text(self.name, 'en')

        if not self.description_uz:
            self.description_uz = translate_text(self.description, 'uz')
        if not self.description_ru:
            self.description_ru = translate_text(self.description, 'ru')
        if not self.description_en:
            self.description_en = translate_text(self.description, 'en')

        super(Exercise, self).save(*args, **kwargs)

    def __str__(self):
        return self.name


import logging
from django.utils.timezone import now
from celery import shared_task

logger = logging.getLogger(__name__)

class ExerciseCompletion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="exercise_completions")
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="exercise_completions")
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="completions")
    is_completed = models.BooleanField(default=False)
    completion_date = models.DateField(null=True, blank=True)
    exercise_date = models.DateField(null=True, blank=True)
    missed = models.BooleanField(default=False)
    reminder_sent = models.BooleanField(default=False)
    exercise_time = models.DurationField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'session', 'exercise')

    def save(self, *args, **kwargs):
        # Automatically set the completion_date if is_completed becomes True
        if self.is_completed and not self.completion_date:
            self.completion_date = now().date()

        super().save(*args, **kwargs)

        # Trigger session check after saving
        self.check_session_completion()

    def check_session_completion(self):
        """Check if all exercises in the session are completed."""
        total_exercises = self.session.exercises.count()
        completed_exercises = ExerciseCompletion.objects.filter(
            session=self.session, user=self.user, is_completed=True
        ).count()

        if total_exercises == completed_exercises:
            # Update or create the session completion object
            session_completion, created = SessionCompletion.objects.get_or_create(
                user=self.user, session=self.session
            )
            session_completion.is_completed = True
            session_completion.completion_date = now().date()
            session_completion.save()
            logger.info(f"Session {self.session.id} marked as completed for user {self.user.id}")


class Meal(models.Model):
    MEAL_TYPES = (
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('snack', 'Snack'),
        ('dinner', 'Dinner'),
    )

    meal_type = models.CharField(max_length=20, choices=MEAL_TYPES)
    food_name = models.CharField(max_length=255)
    food_name_uz = models.CharField(max_length=255, blank=True, null=True)
    food_name_ru = models.CharField(max_length=255, blank=True, null=True)
    food_name_en = models.CharField(max_length=255, blank=True, null=True)
    calories = models.DecimalField(max_digits=5, decimal_places=2, help_text="Calories for this meal")
    water_content = models.DecimalField(max_digits=5, decimal_places=2, help_text="Water content in ml")
    food_photo = models.ImageField(upload_to='meal_photos/', blank=True, null=True)
    preparation_time = models.IntegerField(help_text="Preparation time in minutes")
    meal_type_uz = models.CharField(max_length=20, blank=True, null=True)
    meal_type_ru = models.CharField(max_length=20, blank=True, null=True)
    meal_type_en = models.CharField(max_length=20, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Tarjima qilish
        if not self.food_name_uz:
            self.food_name_uz = translate_text(self.food_name, 'uz')
        if not self.food_name_ru:
            self.food_name_ru = translate_text(self.food_name, 'ru')
        if not self.food_name_en:
            self.food_name_en = translate_text(self.food_name, 'en')

        if not self.meal_type_uz:
            self.meal_type_uz = translate_text(dict(self.MEAL_TYPES).get(self.meal_type), 'uz')
        if not self.meal_type_ru:
            self.meal_type_ru = translate_text(dict(self.MEAL_TYPES).get(self.meal_type), 'ru')
        if not self.meal_type_en:
            self.meal_type_en = translate_text(dict(self.MEAL_TYPES).get(self.meal_type), 'en')

        super(Meal, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.meal_type.capitalize()} for {self.session.user} on {self.session.date}"


class MealCompletion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="meal_completions")
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="meal_completions")
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name="completions")
    is_completed = models.BooleanField(default=False)
    completion_date = models.DateField(null=True, blank=True)
    meal_date = models.DateField(null=True, blank=True)  # New field for planned date
    missed = models.BooleanField(default=False) # Track if the meal was missed
    reminder_sent = models.BooleanField(default=False) # Track if a reminder was sent for this meal
    meal_time = models.TimeField(null=True, blank=True) # Time set by user for meal completion



    class Meta:
        unique_together = ('user', 'session', 'meal')  # Ensures unique tracking per user-session-meal combination

    def save(self, *args, **kwargs):
        if self.is_completed and not self.completion_date:
            self.completion_date = timezone.now().date()
        super(MealCompletion, self).save(*args, **kwargs)

    def __str__(self):
        status = "Completed" if self.is_completed else "Pending"
        return f"{self.user.email_or_phone} - {self.meal.food_name} ({status})"


class Preparation(models.Model):
    meal = models.ForeignKey(
        Meal, on_delete=models.CASCADE, related_name="preparations", verbose_name=_("Meal")
    )

    # Name fields with multi-language support
    name = models.CharField(max_length=255, verbose_name=_("Preparation Name"))
    name_uz = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Name (Uzbek)"))
    name_ru = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Name (Russian)"))
    name_en = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Name (English)"))

    # Description fields with multi-language support
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    description_uz = models.TextField(blank=True, null=True, verbose_name=_("Description (Uzbek)"))
    description_ru = models.TextField(blank=True, null=True, verbose_name=_("Description (Russian)"))
    description_en = models.TextField(blank=True, null=True, verbose_name=_("Description (English)"))

    # Additional Fields
    preparation_time = models.IntegerField(
        default=0, help_text=_("Preparation time in minutes"), verbose_name=_("Preparation Time")
    )
    calories = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00, help_text=_("Total calories"), verbose_name=_("Calories")
    )
    water_usage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00, help_text=_("Water usage in liters"), verbose_name=_("Water Usage")
    )
    video_url = models.URLField(
        max_length=500, blank=True, null=True, verbose_name=_("Video URL")
    )

    def save(self, *args, **kwargs):
        # Automatically translate the name into multiple languages
        if self.name:
            if not self.name_uz:
                self.name_uz = translate_text(self.name, 'uz')
            if not self.name_ru:
                self.name_ru = translate_text(self.name, 'ru')
            if not self.name_en:
                self.name_en = translate_text(self.name, 'en')

        # Automatically translate the description into multiple languages
        if self.description:
            if not self.description_uz:
                self.description_uz = translate_text(self.description, 'uz')
            if not self.description_ru:
                self.description_ru = translate_text(self.description, 'ru')
            if not self.description_en:
                self.description_en = translate_text(self.description, 'en')

        super(Preparation, self).save(*args, **kwargs)

    class Meta:
        verbose_name = _("Preparation")
        verbose_name_plural = _("Preparations")

    def __str__(self):
        return f"{self.name} ({self.meal.food_name})"


class PreparationSteps(models.Model):
    preparation = models.ForeignKey(
        Preparation, on_delete=models.CASCADE, related_name="steps", verbose_name=_("Preparation")
    )

    # Step titles with multi-language support
    title = models.CharField(max_length=255, verbose_name=_("Step Title"))
    title_uz = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Step Title (Uzbek)"))
    title_ru = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Step Title (Russian)"))
    title_en = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Step Title (English)"))

    # Step descriptions with multi-language support
    text = models.TextField(blank=True, null=True, verbose_name=_("Step Description"))
    text_uz = models.TextField(blank=True, null=True, verbose_name=_("Step Description (Uzbek)"))
    text_ru = models.TextField(blank=True, null=True, verbose_name=_("Step Description (Russian)"))
    text_en = models.TextField(blank=True, null=True, verbose_name=_("Step Description (English)"))

    # Step ordering
    step_number = models.PositiveIntegerField(default=1, verbose_name=_("Step Number"))

    # Step time
    step_time = models.CharField(max_length=10, blank=True, null=True, verbose_name=_("Step Time (minutes)"))

    def save(self, *args, **kwargs):
        # Avtomatik step_numberni aniqlash
        if not self.pk:  # Yangi obyekt yaratilganda
            last_step = PreparationSteps.objects.filter(preparation=self.preparation).order_by('step_number').last()
            self.step_number = last_step.step_number + 1 if last_step else 1

        # Tarjima qilish
        if self.title:
            if not self.title_uz:
                self.title_uz = translate_text(self.title, 'uz')
            if not self.title_ru:
                self.title_ru = translate_text(self.title, 'ru')
            if not self.title_en:
                self.title_en = translate_text(self.title, 'en')

        if self.text:
            if not self.text_uz:
                self.text_uz = translate_text(self.text, 'uz')
            if not self.text_ru:
                self.text_ru = translate_text(self.text, 'ru')
            if not self.text_en:
                self.text_en = translate_text(self.text, 'en')

        super(PreparationSteps, self).save(*args, **kwargs)

    class Meta:
        verbose_name = _("Preparation Step")
        verbose_name_plural = _("Preparation Steps")
        ordering = ['step_number']  # Step tartib raqamiga ko‘ra tartiblangan


    class Meta:
        verbose_name = _("Preparation Step")
        verbose_name_plural = _("Preparation Steps")
        ordering = ["step_number"]
        unique_together = ('preparation', 'step_number')  # Ensures no duplicate step numbers per preparation

    def __str__(self):
        return f"Step {self.step_number} for {self.preparation.name}"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    message_uz = models.TextField(blank=True, null=True)
    message_ru = models.TextField(blank=True, null=True)
    message_en = models.TextField(blank=True, null=True)
    language = models.CharField(max_length=10, default='en')
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    notification_type = models.CharField(max_length=50, default="general")  # e.g., "reminder", "update"
    scheduled_time = models.TimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.message_uz:
            self.message_uz = translate_text(self.message, 'uz')
        if not self.message_ru:
            self.message_ru = translate_text(self.message, 'ru')
        if not self.message_en:
            self.message_en = translate_text(self.message, 'en')
        super(Notification, self).save(*args, **kwargs)

    def __str__(self):
        return f"Notification for {self.user.email_or_phone} - {self.sent_at}"







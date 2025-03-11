from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group, Permission
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from googletrans import Translator
from django.utils import timezone
from django.utils.timezone import now
from datetime import timedelta





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



class UserSubscription(models.Model):
    """
    Tracks actual subscription payments and durations separately from sessions.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="subscriptions")
    subscription_type = models.CharField(
        max_length=20,
        choices=[('month', 'Monthly'), ('quarter', '3-Month'), ('year', 'Yearly')],
        default='month'
    )
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        """
        ✅ Automatically sets the correct `end_date` based on subscription type.
        ✅ Prevents expired subscriptions from being marked active.
        """
        if not self.end_date:
            add_days = {
                'month': 30,
                'quarter': 90,
                'year': 365
            }.get(self.subscription_type, 30)

            self.end_date = self.start_date + timedelta(days=add_days)

        # Ensure subscription is not active if expired
        if self.end_date < timezone.now().date():
            self.is_active = False

        super(UserSubscription, self).save(*args, **kwargs)

    def is_subscription_active(self):
        """
        ✅ Checks if the subscription is still valid.
        """
        return self.is_active and self.end_date >= timezone.now().date()

    def extend_subscription(self, add_days):
        """
        ✅ Extends subscription duration based on additional payments.
        """
        if self.end_date >= timezone.now().date():
            self.end_date += timedelta(days=add_days)
        else:
            self.start_date = timezone.now().date()
            self.end_date = self.start_date + timedelta(days=add_days)
        self.save()

        # 🚀 Auto-create sessions on subscription activation
        from exercise.views import create_sessions_for_user
        create_sessions_for_user(self.user)  # ✅ Call the function to create sessions

    def __str__(self):
        return f"{self.user} - {self.subscription_type} (Active: {self.is_active})"


from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
# Ensure you import your other models if you need them
# from users_app.models import SessionCompletion, Program, User (adjust as needed)

class UserProgram(models.Model):
    """
    Tracks user's selected program and their progress.
    Does NOT manage payments anymore. Payments are handled by `UserSubscription`.
    """
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name="user_programs",
        null=True
    )
    program = models.ForeignKey(
        'Program',
        on_delete=models.CASCADE,
        related_name="user_programs",
        null=True
    )

    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField(null=True, blank=True)
    progress = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    # REMOVE is_paid & subscription_type (Handled in UserSubscription)
    amount = models.IntegerField(blank=True, null=True)
    payment_method = models.CharField(max_length=255, blank=True, null=True)

    @property
    def is_paid(self):
        return self.is_subscription_active()

    def calculate_progress(self):
        """
        Calculates how many sessions are completed vs total sessions in self.program.
        """
        from users_app.models import SessionCompletion  # import inside method to avoid circular imports
        if not self.program:
            return 0

        total_sessions = self.program.total_sessions
        completed_sessions = SessionCompletion.objects.filter(
            user=self.user,
            session__program=self.program,
            is_completed=True
        ).count()

        if total_sessions > 0:
            return (completed_sessions / total_sessions) * 100
        return 0

    def is_subscription_active(self):
        """
        ✅ Check if the user has an active subscription (handled in `UserSubscription`).
        """
        return UserSubscription.objects.filter(user=self.user, is_active=True, end_date__gte=timezone.now().date()).exists()

    def __str__(self):
        """
        Display user's selected program.
        """
        if self.program:
            program_goal = self.program.program_goal
        else:
            program_goal = "No Program"

        return f"{self.user} - {program_goal}"




class Session(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE,related_name="sessions")
    session_number = models.IntegerField(null=False)

    meals = models.ManyToManyField('Meal', related_name='sessions')

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # If this is a newly created Session -> increment Program's total_sessions
        if is_new:
            self.program.total_sessions += 1
            self.program.save()
    def __str__(self):
        return f"Session #{self.session_number} - Program: {self.program.program_goal}"


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
    exercise_time = models.DurationField(null=True, blank=True)
    sequence_number = models.IntegerField(default=1)

    name = models.CharField(max_length=255)
    name_uz = models.CharField(max_length=255, blank=True, null=True)
    name_ru = models.CharField(max_length=255, blank=True, null=True)
    name_en = models.CharField(max_length=255, blank=True, null=True)

    description = models.TextField()
    description_uz = models.TextField(blank=True, null=True)
    description_ru = models.TextField(blank=True, null=True)
    description_en = models.TextField(blank=True, null=True)



    image = models.ImageField(upload_to='exercise_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Always update translation fields, or add a condition comparing new and old values
        self.name_uz = translate_text(self.name, 'uz')
        self.name_ru = translate_text(self.name, 'ru')
        self.name_en = translate_text(self.name, 'en')

        self.description_uz = translate_text(self.description, 'uz')
        self.description_ru = translate_text(self.description, 'ru')
        self.description_en = translate_text(self.description, 'en')

        super(Exercise, self).save(*args, **kwargs)

    def __str__(self):
        return self.name



class ExerciseBlock(models.Model):
    session = models.OneToOneField(
        Session, on_delete=models.CASCADE, related_name='block', blank=True, null=True
    )
    block_name = models.CharField(max_length=255)
    block_name_uz = models.CharField(max_length=255, blank=True, null=True)
    block_name_ru = models.CharField(max_length=255, blank=True, null=True)
    block_name_en = models.CharField(max_length=255, blank=True, null=True)

    block_image = models.ImageField(upload_to='exercise_block_images/', blank=True, null=True)
    block_kkal = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00, help_text="Approx total kkal"
    )
    block_water_amount = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00, help_text="Water amount in ml"
    )
    description = models.TextField(blank=True, null=True)
    description_uz = models.TextField(blank=True, null=True)
    description_ru = models.TextField(blank=True, null=True)
    description_en = models.TextField(blank=True, null=True)

    video_url = models.URLField(blank=True, null=True)
    block_time = models.DurationField(
        blank=True, null=True, help_text="Estimated total time (e.g. HH:MM:SS)"
    )
    calories_burned = models.DecimalField(max_digits=5, decimal_places=2, default=0.00,
                                          help_text="Total calories burned in this block")

    exercises = models.ManyToManyField(Exercise, related_name='blocks', blank=True)

    def save(self, *args, **kwargs):
        # Always update translation fields regardless of previous values
        self.block_name_uz = translate_text(self.block_name, 'uz')
        self.block_name_ru = translate_text(self.block_name, 'ru')
        self.block_name_en = translate_text(self.block_name, 'en')

        if self.description:
            self.description_uz = translate_text(self.description, 'uz')
            self.description_ru = translate_text(self.description, 'ru')
            self.description_en = translate_text(self.description, 'en')
        else:
            self.description_uz = ''
            self.description_ru = ''
            self.description_en = ''

        super(ExerciseBlock, self).save(*args, **kwargs)

    def __str__(self):
        return self.block_name



class ExerciseBlockCompletion(models.Model):
    user = models.ForeignKey(
        'User', on_delete=models.CASCADE, related_name='block_completions'
    )
    block = models.ForeignKey(
        ExerciseBlock, on_delete=models.CASCADE, related_name='completions'
    )
    is_completed = models.BooleanField(default=False)
    completion_date = models.DateField(blank=True, null=True)

    class Meta:
        unique_together = ('user', 'block')

    def save(self, *args, **kwargs):
        if self.is_completed and not self.completion_date:
            self.completion_date = timezone.now().date()
        super().save(*args, **kwargs)
        self.mark_session_completed_if_done()

    def mark_session_completed_if_done(self):
        """
        Because there's only ONE block per session,
        if we complete this block => the Session is also completed.
        """
        if self.is_completed:
            session = self.block.session
            from users_app.models import SessionCompletion  # or import at top

            sc, _ = SessionCompletion.objects.get_or_create(
                user=self.user, session=session
            )
            sc.is_completed = True
            sc.completion_date = timezone.now().date()
            sc.save()





class Meal(models.Model):
    """
    Meal model now contains all fields formerly in Preparation (except water_usage,
    which is removed because water_content already exists).
    """
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

    # Extra fields formerly in Preparation
    description = models.TextField(blank=True, null=True)
    description_uz = models.TextField(blank=True, null=True)
    description_ru = models.TextField(blank=True, null=True)
    description_en = models.TextField(blank=True, null=True)
    video_url = models.URLField(max_length=500, blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.description and not self.description_uz:
            self.description_uz = translate_text(self.description, 'uz')
        if self.description and not self.description_ru:
            self.description_ru = translate_text(self.description, 'ru')
        if self.description and not self.description_en:
            self.description_en = translate_text(self.description, 'en')
        super(Meal, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.meal_type.capitalize()}: {self.food_name}"



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

class MealSteps(models.Model):
    """
    Each Meal can have multiple steps.
    (Replaces the old PreparationSteps model.)
    """
    meal = models.ForeignKey(
        Meal,
        on_delete=models.CASCADE,
        related_name="steps",
        verbose_name=_("Meal")
    )
    title = models.CharField(max_length=255, verbose_name=_("Step Title"))
    title_uz = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Step Title (Uzbek)"))
    title_ru = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Step Title (Russian)"))
    title_en = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Step Title (English)"))
    text = models.TextField(blank=True, null=True, verbose_name=_("Step Description"))
    text_uz = models.TextField(blank=True, null=True, verbose_name=_("Step Description (Uzbek)"))
    text_ru = models.TextField(blank=True, null=True, verbose_name=_("Step Description (Russian)"))
    text_en = models.TextField(blank=True, null=True, verbose_name=_("Step Description (English)"))
    step_number = models.PositiveIntegerField(default=1, verbose_name=_("Step Number"))
    step_time = models.CharField(max_length=10, blank=True, null=True, verbose_name=_("Step Time (minutes)"))

    class Meta:
        verbose_name = _("Meal Step")
        verbose_name_plural = _("Meal Steps")
        ordering = ["step_number"]
        unique_together = ('meal', 'step_number')

    def save(self, *args, **kwargs):
        if not self.pk:
            last_step = MealSteps.objects.filter(meal=self.meal).order_by('step_number').last()
            self.step_number = (last_step.step_number + 1) if last_step else 1
        if self.title and not self.title_uz:
            self.title_uz = translate_text(self.title, 'uz')
        if self.title and not self.title_ru:
            self.title_ru = translate_text(self.title, 'ru')
        if self.title and not self.title_en:
            self.title_en = translate_text(self.title, 'en')
        if self.text and not self.text_uz:
            self.text_uz = translate_text(self.text, 'uz')
        if self.text and not self.text_ru:
            self.text_ru = translate_text(self.text, 'ru')
        if self.text and not self.text_en:
            self.text_en = translate_text(self.text, 'en')
        super(MealSteps, self).save(*args, **kwargs)

    def __str__(self):
        return f"Step {self.step_number} for Meal {self.meal.food_name}"



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







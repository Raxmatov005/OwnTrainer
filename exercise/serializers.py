from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from users_app.models import (Program, Session, Exercise, WorkoutCategory, UserProgress, Meal, UserProgram, SessionCompletion, ExerciseCompletion)
from googletrans import Translator
from datetime import timedelta
from threading import Timer
from django.utils.timezone import now

translator = Translator()


def translate_field(instance, field_name, language):
    translated_field = f"{field_name}_{language}"
    if hasattr(instance, translated_field):
        return getattr(instance, translated_field) or getattr(instance, field_name)
    return getattr(instance, field_name)


class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = [
            'id', 'frequency_per_week', 'total_sessions',
            'program_goal', 'is_active'
        ]
        extra_kwargs = {
            'frequency_per_week': {'label': _("Frequency per Week")},
            'total_sessions': {'label': _("Total Sessions")},
            'program_goal': {'label': _("Program Goal")},
            'is_active': {'label': _("Is Active")},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get('language', 'en')
        data['program_goal'] = translate_field(instance, 'program_goal', language)
        return data


class SessionSerializer(serializers.ModelSerializer):
    exercises = serializers.PrimaryKeyRelatedField(queryset=Exercise.objects.all(), many=True)  # bu oldin exercises edi
    meals = serializers.PrimaryKeyRelatedField(queryset=Meal.objects.all(), many=True)

    class Meta:
        model = Session
        fields = [
            'id', 'cover_image', 'program', 'calories_burned',
            'session_number', 'session_time', 'exercises', 'meals'
        ]

        extra_kwargs = {
            'cover_image': {'label': _("Cover Image")},
            'calories_burned': {'label': _("Calories Burned")},
            'session_time': {'label': _("Session Time")},
            'session_number': {'label': _("Session Number"), 'read_only': True},  # Read-only to ensure auto-assignment
            'WorkoutCategory': {'label': _("Exercises")},
            'meals': {'label': _("Meals")},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Add more fields for translation or customization if necessary
        return data

    def create(self, validated_data):
        # Get the program from the validated data
        program = validated_data.get('program')

        # Determine the next session number for the program
        last_session = Session.objects.filter(program=program).order_by('-session_number').first()
        validated_data['session_number'] = (last_session.session_number + 1) if last_session else 1

        # Create and return the new session instance
        return super().create(validated_data)


class ExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = [
            'id', 'category', 'name', 'description', 'exercise_time', 'difficulty_level',
            'video_url', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'name': {'label': _("Exercise Name")},
            'description': {'label': _("Description")},
            'exercise_time': {'label': _("Exercise Time")},
            'difficulty_level': {'label': _("Difficulty Level")},
            'video_url': {'label': _("Video URL")},
            'created_at': {'label': _("Created At")},
            'updated_at': {'label': _("Updated At")},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get('language', 'en')
        data['name'] = translate_field(instance, 'name', language)
        data['description'] = translate_field(instance, 'description', language)
        data['difficulty_level'] = translate_field(instance, 'difficulty_level', language)
        return data


class WorkoutCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkoutCategory
        fields = ['id', 'category_name', 'description', 'workout_image']
        extra_kwargs = {
            'category_name': {'label': _("Category Name")},
            'description': {'label': _("Description")},
            'workout_image': {'label': _("Workout Image")},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get('language', 'en')
        data['category_name'] = translate_field(instance, 'category_name', language)
        data['description'] = translate_field(instance, 'description', language)
        return data


class UserProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProgress
        fields = [
            'id', 'user', 'date', 'completed_sessions', 'total_calories_burned',
            'calories_gained', 'missed_sessions', 'week_number', 'program'
        ]
        extra_kwargs = {
            'user': {'read_only': True},
            'date': {'label': "Date"},
            'completed_sessions': {'label': "Completed Sessions"},
            'total_calories_burned': {'label': "Calories Burned"},
            'calories_gained': {'label': "Calories Gained"},
            'missed_sessions': {'label': "Missed Sessions"},
            'week_number': {'label': "Week Number"},
            'program': {'label': "Program", 'read_only': True},
        }


class UserProgramCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserProgram
        fields = ['program']
        extra_kwargs = {'program': {'label': _("Program")}}


class UserProgramSerializer(serializers.ModelSerializer):
    is_paid = serializers.SerializerMethodField()

    class Meta:
        model = UserProgram
        fields = ['id', 'user', 'program', 'start_date', 'end_date', 'progress', 'is_active', 'is_paid']
        extra_kwargs = {
            'user': {'read_only': True, 'label': _("User")},
            'program': {'label': _("Program")},
            'start_date': {'label': _("Start Date")},
            'end_date': {'label': _("End Date")},
            'progress': {'label': _("Progress")},
            'is_active': {'label': _("Is Active")},
        }

    def get_is_paid(self, obj):
        """Check if the user has an active subscription."""
        return obj.is_subscription_active()  # Ensure this method exists in UserProgram


class UserProgramAllSerializer(serializers.ModelSerializer):
    is_paid = serializers.SerializerMethodField()

    class Meta:
        model = UserProgram
        fields = ['id', 'user', 'program', 'start_date', 'end_date', 'progress', 'is_active', 'is_paid']

    def get_is_paid(self, obj):
        """Check if the user has an active subscription."""
        return obj.has_active_subscription()



class UserUpdateProgressSerializer(serializers.Serializer):
    exercise_id = serializers.IntegerField(required=False, help_text="ID of the exercise")
    meal_id = serializers.IntegerField(required=False, help_text="ID of the meal")
    status = serializers.ChoiceField(
        choices=["completed", "skipped"],
        required=True,
        help_text="Status of the progress: 'completed' or 'skipped'"
    )

    def validate(self, data):
        if not data.get("exercise_id") and not data.get("meal_id"):
            raise serializers.ValidationError(
                "Either 'exercise_id' or 'meal_id' must be provided."
            )
        return data


class StartSessionSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(required=True)

    def validate_session_id(self, value):
        # Session mavjudligini tekshirish
        if not Session.objects.filter(id=value).exists():
            raise serializers.ValidationError("Berilgan Session ID mavjud emas.")
        return value


class ProgressRequestSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["daily", "weekly"], required=True)
    date = serializers.DateField(required=True)


class DailyMealSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    preparation_time = serializers.IntegerField()
    calories = serializers.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        model = Meal
        fields = ['id', 'name', 'preparation_time', 'calories']

    def get_name(self, obj):
        request = self.context.get('request')
        lang = getattr(request.user, 'language', 'en') if request and hasattr(request.user, 'language') else 'en'
        if lang == 'uz':
            return obj.food_name_uz or obj.food_name
        elif lang == 'ru':
            return obj.food_name_ru or obj.food_name
        return obj.food_name_en or obj.food_name


class DailySessionCompletionSerializer(serializers.ModelSerializer):
    session_number = serializers.IntegerField(source='session.session_number', read_only=True)
    meals = DailyMealSerializer(source='session.meals', many=True, read_only=True)
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = SessionCompletion
        fields = ['id', 'session_number', 'is_completed', 'completion_date', 'cover_image', 'meals']

    def get_cover_image(self, obj):
        request = self.context.get('request')
        if obj.session.cover_image:
            return request.build_absolute_uri(obj.session.cover_image.url)
        return None


class SessionStartSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(required=True, help_text="Session ID to start")


from rest_framework import serializers
from users_app.models import ExerciseCompletion
from celery import shared_task
from django.utils.timezone import now
from datetime import timedelta

@shared_task
def mark_exercise_as_complete(exercise_completion_id):
    """Background task to mark exercise as complete."""
    try:
        exercise_completion = ExerciseCompletion.objects.get(id=exercise_completion_id)
        exercise_completion.is_completed = True
        exercise_completion.completion_date = now().date()
        exercise_completion.save()
    except ExerciseCompletion.DoesNotExist:
        pass


class ExerciseStartSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(required=True)
    exercise_id = serializers.IntegerField(required=True)

    def validate(self, attrs):
        session_id = attrs.get("session_id")
        exercise_id = attrs.get("exercise_id")
        user = self.context["request"].user

        # Fetch the ExerciseCompletion instance
        exercise_completion = ExerciseCompletion.objects.filter(
            user=user, session_id=session_id, exercise_id=exercise_id
        ).first()

        if not exercise_completion:
            raise serializers.ValidationError("Exercise not found for this session.")
        if exercise_completion.is_completed:
            raise serializers.ValidationError("Exercise already completed.")

        attrs["exercise_completion"] = exercise_completion
        return attrs

    def create(self, validated_data):
        exercise_completion = validated_data["exercise_completion"]
        exercise_duration = exercise_completion.exercise.exercise_time  # DurationField

        # Start the Celery task to complete the exercise after the given duration
        eta_time = now() + exercise_duration
        mark_exercise_as_complete.apply_async((exercise_completion.id,), eta=eta_time)

        return {
            "session_id": exercise_completion.session.id,
            "exercise_id": exercise_completion.exercise.id,
            "start_time": now(),
            "end_time": eta_time,
            "message": "Exercise started successfully. Completion is scheduled."
        }

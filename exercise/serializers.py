from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from users_app.models import (
    Program, Session, Exercise, UserProgress, Meal,
    UserProgram, SessionCompletion, ExerciseBlock
)
from googletrans import Translator
from datetime import timedelta
from threading import Timer
from django.utils.timezone import now
from celery import shared_task

translator = Translator()

def translate_field(instance, field_name, language):
    translated_field = f"{field_name}_{language}"
    # If the translated field exists and has a non-empty value, return it;
    # otherwise, fall back to the original field’s value.
    if hasattr(instance, translated_field):
        return getattr(instance, translated_field) or getattr(instance, field_name)
    return getattr(instance, field_name)

# ------------------------------
# Program Serializer
# ------------------------------
class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = ['id', 'frequency_per_week', 'total_sessions', 'program_goal', 'is_active']
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

# ------------------------------
# Nested Exercise Serializer
# ------------------------------
class NestedExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = ['name', 'sequence_number', 'exercise_time', 'description', 'image']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get('language', 'en')
        data['name'] = translate_field(instance, 'name', language)
        data['description'] = translate_field(instance, 'description', language)
        return data

# ------------------------------
# Nested ExerciseBlock Serializer (Unified)
# ------------------------------
class NestedExerciseBlockSerializer(serializers.ModelSerializer):
    exercises = NestedExerciseSerializer(many=True, required=False)

    class Meta:
        model = ExerciseBlock
        fields = [
            'block_name',
            'block_image',
            'block_kkal',
            'block_water_amount',
            'description',
            'video_url',
            'block_time',
            'calories_burned',  # Admin must supply or calculate this value.
            'exercises',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get('language', 'en')
        data['block_name'] = translate_field(instance, 'block_name', language)
        data['description'] = translate_field(instance, 'description', language)
        return data

    def create(self, validated_data):
        exercises_data = validated_data.pop('exercises', [])
        block = ExerciseBlock.objects.create(**validated_data)
        for ex_data in exercises_data:
            exercise = Exercise.objects.create(**ex_data)
            block.exercises.add(exercise)
        return block

    def update(self, instance, validated_data):
        exercises_data = validated_data.pop('exercises', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if exercises_data is not None:
            instance.exercises.clear()
            for ex_data in exercises_data:
                exercise = Exercise.objects.create(**ex_data)
                instance.exercises.add(exercise)
        return instance

# ------------------------------
# Session Nested Serializer (Unified Creation)
# ------------------------------
class SessionNestedSerializer(serializers.ModelSerializer):
    # 'meals' is still a list of primary keys.
    meals = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Meal.objects.all(), required=False
    )
    # Nested ExerciseBlock creation.
    block = NestedExerciseBlockSerializer(required=True)

    class Meta:
        model = Session
        fields = ['id', 'program', 'session_number', 'meals', 'block']
        extra_kwargs = {
            'session_number': {'read_only': True},
        }

    def create(self, validated_data):
        block_data = validated_data.pop('block')
        meals_data = validated_data.pop('meals', [])
        program = validated_data.get('program')
        # Auto-increment session_number based on the program.
        last_session = Session.objects.filter(program=program).order_by('-session_number').first()
        next_number = (last_session.session_number + 1) if last_session else 1
        validated_data['session_number'] = next_number
        session = Session.objects.create(**validated_data)
        if meals_data:
            session.meals.set(meals_data)
        # Create the nested ExerciseBlock and link it to the session.
        block_serializer = NestedExerciseBlockSerializer(data=block_data, context=self.context)
        block_serializer.is_valid(raise_exception=True)
        block = block_serializer.save()
        block.session = session
        block.save()
        return session

    def update(self, instance, validated_data):
        block_data = validated_data.pop('block', None)
        meals_data = validated_data.pop('meals', None)
        instance = super().update(instance, validated_data)
        if meals_data is not None:
            instance.meals.set(meals_data)
        if block_data is not None:
            if hasattr(instance, 'block') and instance.block:
                block_serializer = NestedExerciseBlockSerializer(
                    instance=instance.block, data=block_data, partial=True, context=self.context
                )
                block_serializer.is_valid(raise_exception=True)
                block_serializer.save()
            else:
                block_serializer = NestedExerciseBlockSerializer(data=block_data, context=self.context)
                block_serializer.is_valid(raise_exception=True)
                block = block_serializer.save()
                block.session = instance
                block.save()
        return instance

# ------------------------------
# UserProgress Serializer (unchanged)
# ------------------------------
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

# ------------------------------
# UserProgram Serializers
# ------------------------------
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
        return obj.is_subscription_active()  # Using the method from UserProgram

class UserProgramAllSerializer(serializers.ModelSerializer):
    is_paid = serializers.SerializerMethodField()

    class Meta:
        model = UserProgram
        fields = ['id', 'user', 'program', 'start_date', 'end_date', 'progress', 'is_active', 'is_paid']

    def get_is_paid(self, obj):
        return obj.has_active_subscription()  # Ensure this method exists if needed

# ------------------------------
# Other Utility Serializers
# ------------------------------
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
            raise serializers.ValidationError("Either 'exercise_id' or 'meal_id' must be provided.")
        return data

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
        if hasattr(obj.session, 'cover_image') and obj.session.cover_image:
            return request.build_absolute_uri(obj.session.cover_image.url)
        return None



class EmptyQuerySerializer(serializers.Serializer):
    """
    An empty serializer used to override query parameter generation for GET endpoints.
    """
    pass

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
from drf_extra_fields.fields import Base64ImageField

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
    total_sessions = serializers.SerializerMethodField()
    class Meta:
        model = Program
        fields = ['id', 'total_sessions', 'program_goal', 'is_active']
        extra_kwargs = {
            'program_goal': {'label': _("Program Goal")},
            'is_active': {'label': _("Is Active")},
        }

    def get_total_sessions(self, obj):
        """ Dynamically count sessions instead of storing it in the database. """
        return obj.sessions.count()
    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get('language', 'en')
        data['program_goal'] = translate_field(instance, 'program_goal', language)
        return data


# class NestedExerciseSerializer(serializers.ModelSerializer):
#     """
#     Includes `image` so each exercise can have its own image.
#     """
#     image = serializers.ImageField(required=False, allow_null=True)
#
#     class Meta:
#         model = Exercise
#         fields = ['id', 'name', 'sequence_number', 'exercise_time', 'description', 'image']
#         read_only_fields = ['id', 'sequence_number']
#
#     def to_representation(self, instance):
#         data = super().to_representation(instance)
#         language = self.context.get('language', 'en')
#         data['name'] = translate_field(instance, 'name', language)
#         data['description'] = translate_field(instance, 'description', language)
#         return data
#
#
# class NestedExerciseBlockSerializer(serializers.ModelSerializer):
#     """
#     Includes `block_image` at the top level, plus a nested array of `exercises`,
#     each of which can have an `image`.
#     """
#     block_image = serializers.ImageField(required=False, allow_null=True)
#     exercises = NestedExerciseSerializer(many=True, required=False)
#
#     class Meta:
#         model = ExerciseBlock
#         fields = [
#             'id',
#             'block_name',
#             'block_image',
#             'block_kkal',
#             'block_water_amount',
#             'description',
#             'video_url',
#             'block_time',
#             'calories_burned',
#             'exercises'
#         ]
#         read_only_fields = ['id']
#
#     def to_representation(self, instance):
#         data = super().to_representation(instance)
#         language = self.context.get('language', 'en')
#         data['block_name'] = translate_field(instance, 'block_name', language)
#         data['description'] = translate_field(instance, 'description', language)
#         return data
#
#     def create(self, validated_data):
#         exercises_data = validated_data.pop('exercises', [])
#         block = ExerciseBlock.objects.create(**validated_data)
#         for idx, ex_data in enumerate(exercises_data, start=1):
#             ex_data['sequence_number'] = idx
#             exercise = Exercise.objects.create(**ex_data)
#             block.exercises.add(exercise)
#         return block
#
#     def update(self, instance, validated_data):
#         exercises_data = validated_data.pop('exercises', None)
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()
#
#         if exercises_data is not None:
#             existing_exercises = {ex.id: ex for ex in instance.exercises.all()}
#             for idx, ex_data in enumerate(exercises_data, start=1):
#                 ex_id = ex_data.get('id')
#                 if ex_id and ex_id in existing_exercises:
#                     # Update existing exercise
#                     exercise_instance = existing_exercises[ex_id]
#                     for field, val in ex_data.items():
#                         if field == 'id':
#                             continue
#                         setattr(exercise_instance, field, val)
#                     exercise_instance.sequence_number = idx
#                     exercise_instance.save()
#                 else:
#                     # Create new exercise
#                     ex_data['sequence_number'] = idx
#                     new_exercise = Exercise.objects.create(**ex_data)
#                     instance.exercises.add(new_exercise)
#
#         return instance




class SessionPKSerializer(serializers.ModelSerializer):
    # Instead of nested data, use primary key references.
    block = serializers.PrimaryKeyRelatedField(
        queryset=ExerciseBlock.objects.all(), required=False,
        help_text="ID of an existing exercise block to attach to this session."
    )
    meals = serializers.PrimaryKeyRelatedField(
        queryset=Meal.objects.all(), many=True, required=False,
        help_text="List of meal IDs to attach to this session."
    )

    class Meta:
        model = Session
        fields = ['id', 'program', 'session_number', 'block', 'meals']
        extra_kwargs = {'session_number': {'read_only': True}}

    def create(self, validated_data):
        # Pop the block and meals (if provided) from the validated_data.
        block = validated_data.pop('block', None)
        meals = validated_data.pop('meals', [])

        # Determine session number based on the program.
        program = validated_data.get('program')
        last_session = Session.objects.filter(program=program).order_by('-session_number').first()
        next_number = (last_session.session_number + 1) if last_session else 1
        validated_data['session_number'] = next_number

        # Create the session.
        session = Session.objects.create(**validated_data)

        # If a block ID was provided, attach that block to the session.
        if block:
            block.session = session  # because ExerciseBlock has a OneToOneField to Session
            block.save()

        # Set the many-to-many meals if provided.
        if meals:
            session.meals.set(meals)

        return session

    def update(self, instance, validated_data):
        block = validated_data.pop('block', None)
        meals = validated_data.pop('meals', None)
        instance = super().update(instance, validated_data)

        if block is not None:
            block.session = instance
            block.save()
        if meals is not None:
            instance.meals.set(meals)
        return instance


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


class ExerciseListSerializer(serializers.ModelSerializer):
    """
    For listing exercises.
    No `image` field here, just a read-only URL if you want.
    We'll rename the field to `image_url`.
    """
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Exercise
        fields = ['id', 'name', 'sequence_number', 'exercise_time', 'description', 'image_url']
        read_only_fields = ['id', 'sequence_number']

    def get_image_url(self, obj):
        """Return an absolute URL if obj.image is set."""
        if not obj.image:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get('language', 'en')
        data['name'] = translate_field(instance, 'name', language)
        data['description'] = translate_field(instance, 'description', language)
        return data


class ExerciseDetailSerializer(serializers.ModelSerializer):
    """
    For retrieving a single Exercise. Also shows only image_url, not a file field.
    """
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Exercise
        fields = ['id', 'name', 'sequence_number', 'exercise_time', 'description', 'image_url']
        read_only_fields = ['id', 'sequence_number']

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get('language', 'en')
        data['name'] = translate_field(instance, 'name', language)
        data['description'] = translate_field(instance, 'description', language)
        return data


class ExerciseCreateUpdateSerializer(serializers.ModelSerializer):
    """
    JSON-based create/update.
    No `image` field here. We upload or replace the image in a separate endpoint.
    """
    class Meta:
        model = Exercise
        fields = ['id', 'name', 'sequence_number', 'exercise_time', 'description']
        read_only_fields = ['id', 'sequence_number']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get('language', 'en')
        data['name'] = translate_field(instance, 'name', language)
        data['description'] = translate_field(instance, 'description', language)
        return data


class ExerciseBlockListSerializer(serializers.ModelSerializer):
    """
    For listing ExerciseBlocks.
    We'll show `block_image_url` but not an ImageField.
    We'll show nested exercises via the simpler `ExerciseListSerializer`, also with only image_url.
    """
    block_image_url = serializers.SerializerMethodField()
    exercises = ExerciseListSerializer(many=True, read_only=True)

    class Meta:
        model = ExerciseBlock
        fields = [
            'id',
            'block_name',
            'block_image_url',
            'block_kkal',
            'block_water_amount',
            'description',
            'video_url',
            'block_time',
            'calories_burned',
            'exercises',
        ]

    def get_block_image_url(self, obj):
        if not obj.block_image:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.block_image.url)
        return obj.block_image.url

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get('language', 'en')
        data['block_name'] = translate_field(instance, 'block_name', language)
        data['description'] = translate_field(instance, 'description', language)
        return data


class ExerciseBlockDetailSerializer(serializers.ModelSerializer):
    """
    For retrieving a single block detail, same concept.
    """
    block_image_url = serializers.SerializerMethodField()
    exercises = ExerciseDetailSerializer(many=True, read_only=True)

    class Meta:
        model = ExerciseBlock
        fields = [
            'id',
            'block_name',
            'block_image_url',
            'block_kkal',
            'block_water_amount',
            'description',
            'video_url',
            'block_time',
            'calories_burned',
            'exercises',
        ]

    def get_block_image_url(self, obj):
        if not obj.block_image:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.block_image.url)
        return obj.block_image.url

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get('language', 'en')
        data['block_name'] = translate_field(instance, 'block_name', language)
        data['description'] = translate_field(instance, 'description', language)
        return data


class ExerciseBlockCreateUpdateSerializer(serializers.ModelSerializer):
    """
    JSON-based create/update for an ExerciseBlock.
    No 'block_image' or nested 'image' here.
    We'll do nested exercises in JSON only, excluding image field.
    """
    # For nested creation: use the simpler "ExerciseCreateUpdateSerializer"
    exercises = ExerciseCreateUpdateSerializer(many=True, required=False)

    class Meta:
        model = ExerciseBlock
        fields = [
            'id',
            'block_name',
            'block_kkal',
            'block_water_amount',
            'description',
            'video_url',
            'block_time',
            'calories_burned',
            'exercises'
        ]
        read_only_fields = ['id']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get('language', 'en')
        data['block_name'] = translate_field(instance, 'block_name', language)
        data['description'] = translate_field(instance, 'description', language)
        return data

    def create(self, validated_data):
        exercises_data = validated_data.pop('exercises', [])
        block = ExerciseBlock.objects.create(**validated_data)
        for idx, ex_data in enumerate(exercises_data, start=1):
            ex_data['sequence_number'] = idx
            exercise = Exercise.objects.create(**ex_data)
            block.exercises.add(exercise)
        return block

    def update(self, instance, validated_data):
        exercises_data = validated_data.pop('exercises', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if exercises_data is not None:
            existing_exercises = {ex.id: ex for ex in instance.exercises.all()}
            for idx, ex_data in enumerate(exercises_data, start=1):
                ex_id = ex_data.get('id')
                if ex_id and ex_id in existing_exercises:
                    exercise_instance = existing_exercises[ex_id]
                    for field, val in ex_data.items():
                        if field != 'id':
                            setattr(exercise_instance, field, val)
                    exercise_instance.sequence_number = idx
                    exercise_instance.save()
                else:
                    ex_data['sequence_number'] = idx
                    new_exercise = Exercise.objects.create(**ex_data)
                    instance.exercises.add(new_exercise)

        return instance

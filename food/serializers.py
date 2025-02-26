from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from googletrans import Translator
from django.utils.timezone import now
from users_app.models import Meal, MealSteps, MealCompletion, Session

translator = Translator()

def translate_field(instance, field_name, language):
    translated_field = f"{field_name}_{language}"
    val = getattr(instance, translated_field, None)
    return val if val else getattr(instance, field_name, '')








# --- Existing Output Serializers (unchanged) ---
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import Meal, MealSteps

# --- Output Serializers ---

class MealStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealSteps
        fields = ['id', 'title', 'text', 'step_time', 'step_number']
        read_only_fields = ['id', 'step_number']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get("language", "en")
        # Example translation logic; adjust as needed
        data['title'] = getattr(instance, f"title_{language}", instance.title)
        data['text'] = getattr(instance, f"text_{language}", instance.text)
        return data

class MealNestedSerializer(serializers.ModelSerializer):
    steps = MealStepSerializer(many=True, required=False)
    food_photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Meal
        fields = [
            'id',
            'meal_type',
            'food_name',
            'calories',
            'water_content',
            'food_photo',
            'preparation_time',
            'description',
            'video_url',
            'steps'
        ]
        read_only_fields = ['id']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        language = self.context.get("language", "en")
        data['meal_type'] = getattr(instance, f"meal_type_{language}", None) or instance.get_meal_type_display()
        data['food_name'] = getattr(instance, f"food_name_{language}", instance.food_name)
        data['description'] = getattr(instance, f"description_{language}", instance.description)
        if instance.food_photo:
            try:
                data['food_photo'] = request.build_absolute_uri(instance.food_photo.url) if request else instance.food_photo.url
            except Exception:
                data['food_photo'] = None
        else:
            data['food_photo'] = None
        return data

    def create(self, validated_data):
        steps_data = validated_data.pop('steps', [])
        meal = Meal.objects.create(**validated_data)
        for step_data in steps_data:
            MealSteps.objects.create(meal=meal, **step_data)
        return meal

    def update(self, instance, validated_data):
        steps_data = validated_data.pop('steps', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if steps_data is not None:
            existing_steps = {step.id: step for step in instance.steps.all()}
            for step_data in steps_data:
                step_id = step_data.get('id')
                if step_id and step_id in existing_steps:
                    step_instance = existing_steps[step_id]
                    for attr, value in step_data.items():
                        setattr(step_instance, attr, value)
                    step_instance.save()
                else:
                    MealSteps.objects.create(meal=instance, **step_data)
        return instance

# --- Create (Input) Serializers ---

class MealStepCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealSteps
        fields = ['title', 'text', 'step_time']

class MealCreateSerializer(serializers.ModelSerializer):
    # Note: The file field is at the root.
    steps = MealStepCreateSerializer(many=True, required=False)
    food_photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Meal
        fields = [
            'meal_type',
            'food_name',
            'calories',
            'water_content',
            'food_photo',
            'preparation_time',
            'description',
            'video_url',
            'steps'
        ]

    def create(self, validated_data):
        steps_data = validated_data.pop('steps', [])
        meal = Meal.objects.create(**validated_data)
        for step_data in steps_data:
            MealSteps.objects.create(meal=meal, **step_data)
        return meal


class MealCompletionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealCompletion
        fields = ['id', 'meal', 'session', 'is_completed', 'completion_date', 'meal_time']

class CompleteMealSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(required=True)
    meal_id = serializers.IntegerField(required=True)

class MealDetailSerializer(serializers.ModelSerializer):
    steps = MealStepSerializer(many=True, read_only=True)
    class Meta:
        model = Meal
        fields = [
            'id',
            'meal_type',
            'food_name',
            'calories',
            'water_content',
            'food_photo',
            'preparation_time',
            'description',
            'video_url',
            'steps'
        ]
    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request', None)
        language = self.context.get("language", "en")
        data['meal_type'] = getattr(instance, f"meal_type_{language}", None) or instance.get_meal_type_display()
        data['food_name'] = translate_field(instance, 'food_name', language)
        data['description'] = translate_field(instance, 'description', language)
        if instance.food_photo and request is not None:
            data['food_photo'] = request.build_absolute_uri(instance.food_photo.url)
        elif instance.food_photo:
            data['food_photo'] = instance.food_photo.url
        else:
            data['food_photo'] = None
        return data

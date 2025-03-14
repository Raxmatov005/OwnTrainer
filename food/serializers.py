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







class MealStepListSerializer(serializers.ModelSerializer):
    """
    For listing steps. We'll keep it simple (no file fields).
    """
    class Meta:
        model = MealSteps
        fields = ['id', 'title', 'step_time', 'step_number']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get("language") or (self.context.get("request").user.language if self.context.get("request") else "en")
        data['title'] = translate_field(instance, 'title', language)
        return data

class MealStepDetailSerializer(serializers.ModelSerializer):
    """
    For retrieving a single step if needed. No file fields anyway.
    """
    class Meta:
        model = MealSteps
        fields = ['id', 'title', 'text', 'step_time', 'step_number']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get("language") or (self.context.get("request").user.language if self.context.get("request") else "en")
        data['title'] = translate_field(instance, 'title', language)
        data['text'] = translate_field(instance, 'text', language)
        return data


class MealListSerializer(serializers.ModelSerializer):
    """
    For listing meals. We'll show a 'food_photo_url' instead of an ImageField.
    """
    food_photo_url = serializers.SerializerMethodField()
    steps = serializers.SerializerMethodField()  # if you want a brief step list

    class Meta:
        model = Meal
        fields = [
            'id',
            'meal_type',
            'food_name',
            'calories',
            'water_content',
            'preparation_time',
            'description',
            'video_url',
            'food_photo_url',
            'steps'
        ]

    def get_food_photo_url(self, obj):
        if not obj.food_photo:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.food_photo.url)
        return obj.food_photo.url

    def get_steps(self, obj):
        steps = obj.steps.all()
        language = self.context.get("language") or (self.context.get("request").user.language if self.context.get("request") else "en")
        return [
            {
                "id": s.id,
                "title": translate_field(s, 'title', language),
                "text": translate_field(s, 'text', language),  # Added field
                "step_time": s.step_time,  # Added field
                "step_number": s.step_number
            }
            for s in steps
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get("language") or (self.context.get("request").user.language if self.context.get("request") else "en")
        data['meal_type'] = getattr(instance, f"meal_type_{language}", None) or instance.get_meal_type_display()
        data['food_name'] = translate_field(instance, 'food_name', language)
        data['description'] = translate_field(instance, 'description', language)
        return data

class MealDetailSerializer(serializers.ModelSerializer):
    """
    For retrieving a single meal. Also uses food_photo_url instead of the actual file.
    """
    food_photo_url = serializers.SerializerMethodField()
    steps = MealStepDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Meal
        fields = [
            'id',
            'meal_type',
            'food_name',
            'calories',
            'water_content',
            'preparation_time',
            'description',
            'video_url',
            'food_photo_url',
            'steps'
        ]


    def get_food_photo_url(self, obj):
        if not obj.food_photo:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.food_photo.url)
        return obj.food_photo.url

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get("language") or (
            self.context.get("request").user.language if self.context.get("request") else "en")

        data['meal_type'] = getattr(instance, f"meal_type_{language}", None) or instance.get_meal_type_display()
        data['food_name'] = translate_field(instance, 'food_name', language)
        data['description'] = translate_field(instance, 'description', language)
        return data


# food/serializers.py

class MealCreateUpdateSerializer(serializers.ModelSerializer):
    """
    JSON-only create/update for Meal. 'food_photo' excluded.
    We'll handle steps in a separate endpoint (MealStepViewSet).
    """
    class Meta:
        model = Meal
        fields = [
            'id',
            'meal_type',
            'food_name',
            'calories',
            'water_content',
            'preparation_time',
            'description',
            'video_url',
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        # Just create the Meal itself
        meal = Meal.objects.create(**validated_data)
        return meal

    def update(self, instance, validated_data):
        # Update Meal fields only
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class MealCompletionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealCompletion
        fields = ['id', 'meal', 'session', 'is_completed', 'completion_date', 'meal_time']

class CompleteMealSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(required=True)
    meal_id = serializers.IntegerField(required=True)



class MealImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meal
        fields = ['food_photo']
        extra_kwargs = {
            'food_photo': {
                'required': True,
                'error_messages': {'required': 'Food photo is required.'}
            }
        }

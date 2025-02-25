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

class MealStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealSteps
        fields = ['id', 'title', 'text', 'step_time', 'step_number']
        read_only_fields = ['id', 'step_number']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get("language", "en")
        data['title'] = translate_field(instance, 'title', language)
        data['text'] = translate_field(instance, 'text', language)
        return data

class MealNestedSerializer(serializers.ModelSerializer):
    steps = MealStepSerializer(many=True, required=False)
    food_photo = serializers.ImageField(required=False, allow_null=True)  # ✅ Ensure `food_photo` is defined

    class Meta:
        model = Meal
        fields = [
            'id',
            'meal_type',
            'food_name',
            'calories',
            'water_content',
            'food_photo',  # ✅ Ensure this field is listed
            'preparation_time',
            'description',
            'video_url',
            'steps'
        ]
        read_only_fields = ['id']

    def to_representation(self, instance):
        """✅ Ensure `food_photo` is always included in API responses"""
        data = super().to_representation(instance)
        request = self.context.get('request', None)
        language = self.context.get("language", "en")

        data['meal_type'] = getattr(instance, f"meal_type_{language}", None) or instance.get_meal_type_display()
        data['food_name'] = translate_field(instance, 'food_name', language)
        data['description'] = translate_field(instance, 'description', language)

        # ✅ Ensure `food_photo` is always a valid URL
        if instance.food_photo:
            try:
                if request is not None:
                    data['food_photo'] = request.build_absolute_uri(instance.food_photo.url)  # Full URL
                else:
                    data['food_photo'] = instance.food_photo.url  # Relative URL
            except ValueError:
                data['food_photo'] = None  # Prevent crashes if file path is invalid
        else:
            data['food_photo'] = None

        return data

    def create(self, validated_data):
        """✅ Explicitly handle `food_photo` to ensure it's processed"""
        request = self.context.get('request')
        food_photo = request.FILES.get('food_photo') if request and 'food_photo' in request.FILES else None

        steps_data = validated_data.pop('steps', [])
        meal = Meal.objects.create(food_photo=food_photo, **validated_data)

        for step_dict in steps_data:
            MealSteps.objects.create(meal=meal, **step_dict)

        return meal

    def update(self, instance, validated_data):
        """✅ Ensure `food_photo` is correctly handled in updates"""
        request = self.context.get('request')
        food_photo = request.FILES.get('food_photo') if request and 'food_photo' in request.FILES else None

        if food_photo:
            instance.food_photo = food_photo  # ✅ Update image if new one is provided

        steps_data = validated_data.pop('steps', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # ✅ Ensure meal steps update correctly
        if steps_data is not None:
            existing_steps = {step.id: step for step in instance.steps.all()}
            for step_dict in steps_data:
                step_id = step_dict.get('id', None)
                if step_id:
                    if step_id in existing_steps:
                        step_instance = existing_steps[step_id]
                        for attr, value in step_dict.items():
                            setattr(step_instance, attr, value)
                        step_instance.save()
                    else:
                        MealSteps.objects.create(meal=instance, **step_dict)
                else:
                    MealSteps.objects.create(meal=instance, **step_dict)

        return instance

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

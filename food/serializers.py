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





# class MealStepSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = MealSteps
#         fields = ['id', 'title', 'text', 'step_time', 'step_number']
#         read_only_fields = ['id', 'step_number']
#
#     def to_representation(self, instance):
#         data = super().to_representation(instance)
#         language = self.context.get("language", "en")
#         data['title'] = translate_field(instance, 'title', language)
#         data['text'] = translate_field(instance, 'text', language)
#         return data
#
#
# class MealNestedSerializer(serializers.ModelSerializer):
#     steps = MealStepSerializer(many=True, required=False)
#     food_photo = serializers.ImageField(required=False, allow_null=True)
#
#     class Meta:
#         model = Meal
#         fields = [
#             'id',
#             'meal_type',
#             'food_name',
#             'calories',
#             'water_content',
#             'food_photo',
#             'preparation_time',
#             'description',
#             'video_url',
#             'steps'
#         ]
#         read_only_fields = ['id']
#
#     def to_representation(self, instance):
#         data = super().to_representation(instance)
#         request = self.context.get('request', None)
#         language = self.context.get("language", "en")
#
#         data['meal_type'] = getattr(instance, f"meal_type_{language}", None) or instance.get_meal_type_display()
#         data['food_name'] = translate_field(instance, 'food_name', language)
#         data['description'] = translate_field(instance, 'description', language)
#
#         if instance.food_photo:
#             try:
#                 if request is not None:
#                     data['food_photo'] = request.build_absolute_uri(instance.food_photo.url)
#                 else:
#                     data['food_photo'] = instance.food_photo.url
#             except ValueError:
#                 data['food_photo'] = None
#         else:
#             data['food_photo'] = None
#
#         return data
#
#     def create(self, validated_data):
#         steps_data = validated_data.pop('steps', [])
#         meal = Meal.objects.create(**validated_data)
#         for step_dict in steps_data:
#             MealSteps.objects.create(meal=meal, **step_dict)
#         return meal
#
#     def update(self, instance, validated_data):
#         steps_data = validated_data.pop('steps', None)
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()
#
#         if steps_data is not None:
#             existing_steps = {s.id: s for s in instance.steps.all()}
#             for step_dict in steps_data:
#                 step_id = step_dict.get('id')
#                 if step_id and step_id in existing_steps:
#                     step_instance = existing_steps[step_id]
#                     for field, val in step_dict.items():
#                         setattr(step_instance, field, val)
#                     step_instance.save()
#                 else:
#                     MealSteps.objects.create(meal=instance, **step_dict)
#         return instance
#
#


class MealStepListSerializer(serializers.ModelSerializer):
    """
    For listing steps. We'll keep it simple (no file fields).
    """
    class Meta:
        model = MealSteps
        fields = ['id', 'title', 'step_time', 'step_number']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get("language", "en")
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
        language = self.context.get("language", "en")
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
        language = self.context.get("language", "en")
        return [
            {
                "id": s.id,
                "title": translate_field(s, 'title', language),
                "step_number": s.step_number
            }
            for s in steps
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get("language", "en")
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
        language = self.context.get("language", "en")
        data['meal_type'] = getattr(instance, f"meal_type_{language}", None) or instance.get_meal_type_display()
        data['food_name'] = translate_field(instance, 'food_name', language)
        data['description'] = translate_field(instance, 'description', language)
        return data


class MealCreateUpdateSerializer(serializers.ModelSerializer):
    """
    JSON-only create/update for Meal. 'food_photo' excluded.
    We'll handle that in a separate upload endpoint.
    """
    steps = MealStepDetailSerializer(many=True, required=False)

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
            'steps'
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        steps_data = validated_data.pop('steps', [])
        meal = Meal.objects.create(**validated_data)
        for step_dict in steps_data:
            MealSteps.objects.create(meal=meal, **step_dict)
        return meal

    def update(self, instance, validated_data):
        steps_data = validated_data.pop('steps', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if steps_data is not None:
            existing_steps = {s.id: s for s in instance.steps.all()}
            for step_dict in steps_data:
                step_id = step_dict.get('id')
                if step_id and step_id in existing_steps:
                    step_instance = existing_steps[step_id]
                    for field, val in step_dict.items():
                        setattr(step_instance, field, val)
                    step_instance.save()
                else:
                    MealSteps.objects.create(meal=instance, **step_dict)
        return instance

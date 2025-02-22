from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from users_app.models import Preparation, Meal, MealCompletion, PreparationSteps, Session
from googletrans import Translator
from django.utils.timezone import now

translator = Translator()

def translate_field(instance, field_name, language):
    translated_field = f"{field_name}_{language}"
    val_translated = getattr(instance, translated_field, None)
    return val_translated if val_translated else getattr(instance, field_name, '')

# -------------------------------
# NestedPreparationStepSerializer
# -------------------------------
class NestedPreparationStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreparationSteps
        fields = ['title', 'text', 'step_time']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get("language", "en")
        data['title'] = translate_field(instance, 'title', language)
        data['text'] = translate_field(instance, 'text', language)
        return data

# -------------------------------
# NestedPreparationSerializer
# -------------------------------
class NestedPreparationSerializer(serializers.ModelSerializer):
    steps = NestedPreparationStepSerializer(many=True, required=False)

    class Meta:
        model = Preparation
        fields = ['name', 'description', 'preparation_time', 'calories', 'water_usage', 'video_url', 'steps']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get("language", "en")
        data['name'] = translate_field(instance, 'name', language)
        data['description'] = translate_field(instance, 'description', language)
        return data

    def create(self, validated_data):
        steps_data = validated_data.pop('steps', [])
        preparation = Preparation.objects.create(**validated_data)
        for step_data in steps_data:
            # We call the NestedPreparationStepSerializer's create method directly.
            NestedPreparationStepSerializer().create({**step_data, 'preparation': preparation})
        return preparation

    def update(self, instance, validated_data):
        steps_data = validated_data.pop('steps', None)
        # Update the preparation's own fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if steps_data is not None:
            # Instead of deleting all steps, update steps with provided IDs and create new ones.
            existing_steps = {step.id: step for step in instance.steps.all()}
            for step_data in steps_data:
                step_id = step_data.get('id', None)
                if step_id and step_id in existing_steps:
                    # Update the existing step.
                    step_instance = existing_steps[step_id]
                    for attr, value in step_data.items():
                        setattr(step_instance, attr, value)
                    step_instance.save()
                else:
                    # Create a new step.
                    NestedPreparationStepSerializer().create({**step_data, 'preparation': instance})
        return instance

# -------------------------------
# MealNestedSerializer
# -------------------------------
class MealNestedSerializer(serializers.ModelSerializer):
    preparations = NestedPreparationSerializer(many=True, required=False)

    class Meta:
        model = Meal
        fields = [
            'food_name', 'preparation_time', 'calories', 'water_content',
            'food_photo', 'description', 'meal_type', 'preparations'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get("language", "en")
        data['food_name'] = translate_field(instance, "food_name", language)
        data['description'] = translate_field(instance, "description", language)
        # For meal_type, if a translated version exists, use it; otherwise, use the display value.
        data['meal_type'] = getattr(instance, f"meal_type_{language}", None) or instance.get_meal_type_display()
        return data

    def create(self, validated_data):
        preparations_data = validated_data.pop('preparations', [])
        meal = Meal.objects.create(**validated_data)
        for prep_data in preparations_data:
            prep_serializer = NestedPreparationSerializer(data=prep_data, context=self.context)
            prep_serializer.is_valid(raise_exception=True)
            preparation = prep_serializer.save()
            meal.preparations.add(preparation)
        return meal

    def update(self, instance, validated_data):
        preparations_data = validated_data.pop('preparations', None)
        instance = super().update(instance, validated_data)
        if preparations_data is not None:
            instance.preparations.clear()
            for prep_data in preparations_data:
                prep_serializer = NestedPreparationSerializer(data=prep_data, context=self.context)
                prep_serializer.is_valid(raise_exception=True)
                preparation = prep_serializer.save()
                instance.preparations.add(preparation)
        return instance

# -------------------------------
# MealCompletionSerializer
# -------------------------------
class MealCompletionSerializer(serializers.ModelSerializer):
    meal_name = serializers.CharField(source='meal.food_name', read_only=True)
    meal_calories = serializers.DecimalField(source='meal.calories', max_digits=5, decimal_places=2, read_only=True)
    session_id = serializers.PrimaryKeyRelatedField(queryset=Session.objects.all(), source='session')

    class Meta:
        model = MealCompletion
        fields = [
            'id', 'meal', 'session_id', 'is_completed', 'completion_date',
            'meal_name', 'meal_calories', 'meal_time'
        ]
        read_only_fields = ['completion_date']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get("language", "en")
        data['meal_name'] = translate_field(instance.meal, 'food_name', language)
        return data

# -------------------------------
# MealDetailSerializer
# -------------------------------
class MealDetailSerializer(serializers.ModelSerializer):
    preparations = PreparationSerializer(many=True, read_only=True)

    class Meta:
        model = Meal
        fields = [
            'id', 'meal_type', 'food_name', 'calories', 'water_content',
            'food_photo', 'preparation_time', 'preparations'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get("language", "en")
        data['meal_type'] = getattr(instance, f'meal_type_{language}', None) or translate_field(instance, 'meal_type', language)
        data['food_name'] = getattr(instance, f'food_name_{language}', None) or translate_field(instance, 'food_name', language)
        return data

# -------------------------------
# CompleteMealSerializer
# -------------------------------
class CompleteMealSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(required=True, help_text="Session ID ni kiriting.")
    meal_id = serializers.IntegerField(required=True, help_text="Meal ID ni kiriting.")

    def validate(self, attrs):
        session_id = attrs.get('session_id')
        meal_id = attrs.get('meal_id')
        if not Session.objects.filter(id=session_id).exists():
            raise serializers.ValidationError(_("Session not found."))
        if not Meal.objects.filter(id=meal_id).exists():
            raise serializers.ValidationError(_("Meal not found."))
        return attrs

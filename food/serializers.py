from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from users_app.models import Preparation, Meal, MealCompletion, Session,PreparationSteps
from googletrans import Translator


translator = Translator()


def translate_text(text, target_language):
    """Translate the text to the specified language using Google Translate."""
    try:
        translation = translator.translate(text, dest=target_language)
        return translation.text
    except Exception as e:
        print(f"Translation error: {e}")
        return text


class PreparationStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreparationSteps
        fields = [
            'id', 'preparation', 'title', 'text', 'step_time', 'step_number',
            'title_uz', 'title_ru', 'title_en', 'text_uz', 'text_ru', 'text_en'
        ]
        extra_kwargs = {
            'title_uz': {'read_only': True},
            'title_ru': {'read_only': True},
            'title_en': {'read_only': True},
            'text_uz': {'read_only': True},
            'text_ru': {'read_only': True},
            'text_en': {'read_only': True},
            'step_number': {'read_only': True},  # step_number avtomatik bo‘lishi uchun
        }

    def create(self, validated_data):
        title = validated_data.get('title', '')
        text = validated_data.get('text', '')

        # Tarjima qilinadigan maydonlar
        validated_data['title_uz'] = translate_text(title, 'uz')
        validated_data['title_ru'] = translate_text(title, 'ru')
        validated_data['title_en'] = translate_text(title, 'en')

        validated_data['text_uz'] = translate_text(text, 'uz')
        validated_data['text_ru'] = translate_text(text, 'ru')
        validated_data['text_en'] = translate_text(text, 'en')

        return super().create(validated_data)

    def to_representation(self, instance):
        """
        Foydalanuvchi tili asosida tarjima qilingan maydonlarni qaytaradi.
        """
        data = super().to_representation(instance)
        language = self.context.get('language', 'en')

        # Asosiy maydonlarni foydalanuvchi tiliga o‘zgartirish
        data['title'] = getattr(instance, f'title_{language}', instance.title)
        data['text'] = getattr(instance, f'text_{language}', instance.text)
        return data


class PreparationSerializer(serializers.ModelSerializer):
    meal = serializers.PrimaryKeyRelatedField(queryset=Meal.objects.all(), required=True)
    steps = PreparationStepSerializer(many=True, read_only=True)  # Steps faqat GET uchun

    class Meta:
        model = Preparation
        fields = [
            'id', 'meal', 'name', 'description', 'preparation_time',
            'calories', 'water_usage', 'video_url', 'steps'
        ]
        extra_kwargs = {
            'name': {'required': True, 'label': _("Name")},
            'description': {'label': _("Description")},
            'preparation_time': {'label': _("Preparation Time")},
            'video_url': {'label': _("Video URL")},
        }

    def create(self, validated_data):
        # Translating name and description during creation
        name = validated_data.get('name', '')
        description = validated_data.get('description', '')

        validated_data['name_uz'] = translate_text(name, 'uz')
        validated_data['name_ru'] = translate_text(name, 'ru')
        validated_data['name_en'] = translate_text(name, 'en')

        validated_data['description_uz'] = translate_text(description, 'uz')
        validated_data['description_ru'] = translate_text(description, 'ru')
        validated_data['description_en'] = translate_text(description, 'en')

        return super().create(validated_data)

    def to_representation(self, instance):
        # Custom representation to return meal ID and translated fields
        data = super().to_representation(instance)
        language = self.context.get('language', 'en')

        # Return only meal ID
        data['meal'] = instance.meal.id

        # Return translated fields based on user language
        data['name'] = getattr(instance, f'name_{language}', instance.name)
        data['description'] = getattr(instance, f'description_{language}', instance.description)

        return data


class MealSerializer(serializers.ModelSerializer):
    session_date = serializers.DateField(source='session.scheduled_date', read_only=True)
    meal_type = serializers.ChoiceField(choices=Meal.MEAL_TYPES, required=True)
    food_photo = serializers.ImageField(required=False, allow_null=True)
    preparations = PreparationSerializer(many=True, read_only=True)
    session_category = serializers.CharField(source='session.category', read_only=True)
    session_exercise_type = serializers.CharField(source='session.exercise_type', read_only=True)

    class Meta:
        model = Meal
        fields = [
            'id', 'session_date', 'meal_type', 'food_name', 'calories',
            'water_content', 'preparation_time', 'food_photo', 'preparations',
            'session_category', 'session_exercise_type'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get("language", "en")

        # Translate meal type
        meal_type_translations = {
            'breakfast': translate_text('Breakfast', language),
            'lunch': translate_text('Lunch', language),
            'snack': translate_text('Snack', language),
            'dinner': translate_text('Dinner', language)
        }
        data['meal_type'] = meal_type_translations.get(instance.meal_type, instance.meal_type)

        # Translate food name
        data['food_name'] = translate_text(instance.food_name, language)

        # Translate linked preparations
        if 'preparations' in data:
            for preparation in data['preparations']:
                preparation['name'] = translate_text(preparation['name'], language)
                preparation['description'] = translate_text(preparation['description'], language)

        return data


class MealCompletionSerializer(serializers.ModelSerializer):
    meal_name = serializers.CharField(source='meal.food_name', read_only=True)
    meal_calories = serializers.DecimalField(source='meal.calories', max_digits=5, decimal_places=2, read_only=True)
    session_id = serializers.PrimaryKeyRelatedField(queryset=Session.objects.all(), source='session')

    class Meta:
        model = MealCompletion
        fields = ['id', 'meal', 'session_id', 'is_completed', 'completion_date', 'meal_name', 'meal_calories', 'meal_time']
        read_only_fields = ['completion_date']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        language = self.context.get("language", "en")

        # Translate meal name
        data['meal_name'] = translate_text(instance.meal.food_name, language)
        return data


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

        # Translate fields dynamically
        data['meal_type'] = getattr(instance, f'meal_type_{language}', None) or translate_text(instance.get_meal_type_display(), language)
        data['food_name'] = getattr(instance, f'food_name_{language}', None) or translate_text(instance.food_name, language)

        return data


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



from django.contrib.auth.password_validation import validate_password
from users_app.models import User, Program, Session, Exercise, Meal, UserProgram
import re
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class InitialRegisterSerializer(serializers.ModelSerializer):
    email_or_phone = serializers.CharField(label=_("Email or Phone"), required=True)
    password = serializers.CharField(write_only=True, label=_("Password"))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email_or_phone', 'password']

    def validate(self, attrs):
        identifier = attrs.get('email_or_phone', '').strip()

        # Ensure an identifier is provided
        if not identifier:
            raise serializers.ValidationError({"email_or_phone": _("Please provide either an email address or a phone number.")})

        # Check if identifier looks like a phone (starts with '+' and only digits)
        phone_regex = re.compile(r'^\+\d+$')
        if phone_regex.match(identifier):
            # It's a phone number
            existing_user_phone = User.objects.filter(email_or_phone=identifier, is_active=True).first()
            if existing_user_phone:
                raise serializers.ValidationError({"email_or_phone": _("This phone number is already registered.")})
        else:
            # Not strictly a phone number, try validating as an email
            validator = EmailValidator()
            try:
                validator(identifier)
            except ValidationError:
                raise serializers.ValidationError({"email_or_phone": _("Invalid email or phone number. Provide a valid email or a phone number starting with '+'.")})


        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.is_active = False  # User starts as inactive
        user.save()
        return user


class CompleteProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['gender', 'country', 'age', 'height', 'weight', 'goal', 'level']
        extra_kwargs = {
            'gender': {'required': True},
            'country': {'required': True},
            'age': {'required': True},
            'height': {'required': True},
            'weight': {'required': True},
            'goal': {'required': True},
            'level': {'required': True},
        }


    def validate_age(self,value):
        if value < 18 or value > 50:
            raise serializers.ValidationError(_("Age must be between 18 and 50 years."))
        return value


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'gender',
            'country',
            'age',
            'height',
            'weight',
            'goal',
            'level',
            'photo',
            'language',
            'phone_or_email_optional',  # Make it optional in the serializer
        ]
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            'phone_or_email_optional': {'required': False, 'allow_null': True, 'allow_blank': True},
        }

    def validate(self, attrs):
        user = self.instance  # Current user instance

        # Determine if user is registered with email or phone
        registered_with_email = '@' in user.email_or_phone
        registered_with_phone = not registered_with_email

        # Get the new optional field value if provided
        optional_field = attrs.get('phone_or_email_optional', None)

        # Only validate if the optional_field has been provided
        if optional_field:
            if registered_with_email:
                # User originally registered with email -> optional field should be phone if provided
                if not optional_field.isdigit():
                    raise serializers.ValidationError(
                        {"phone_or_email_optional": "You must add a valid phone number."}
                    )
            else:
                # User originally registered with phone -> optional field should be email if provided
                if '@' not in optional_field:
                    raise serializers.ValidationError(
                        {"phone_or_email_optional": "You must add a valid email address."}
                    )

        return attrs



class VerifyCodeSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(label=_("User ID"))
    code = serializers.IntegerField(label=_("Verification Code"))

    def validate_code(self, value):
        if not (1000 <= value <= 9999):
            raise serializers.ValidationError(_("Verification code must be a 4-digit number."))
        return value


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        email_or_phone = attrs.get("email_or_phone")
        password = attrs.get("password")

        user = User.objects.filter(email_or_phone=email_or_phone).first()
        if user and user.check_password(password):
            if not user.is_active:
                raise serializers.ValidationError("Account is inactive.")
            return super().validate(attrs)
        else:
            raise serializers.ValidationError("No active account found with the given credentials.")


class LoginSerializer(serializers.Serializer):
    email_or_phone = serializers.CharField(max_length=255, label=_("Email or Phone"))
    password = serializers.CharField(write_only=True, label=_("Password"))


class ForgotPasswordSerializer(serializers.Serializer):
    email_or_phone = serializers.CharField(max_length=255, label=_("Email or Phone"))

    def validate_email_or_phone(self, value):
        phone_regex = r'^\+998\d{9}$'
        if re.match(phone_regex, value):
            return value
        try:
            serializers.EmailField().run_validation(value)
            return value
        except serializers.ValidationError:
            raise serializers.ValidationError(_("Enter a valid phone number or email address."))


class ResetPasswordSerializer(serializers.Serializer):
    email_or_phone = serializers.CharField(max_length=255, label=_("Email or Phone"))
    verification_code = serializers.IntegerField(label=_("Verification Code"))
    new_password = serializers.CharField(write_only=True, max_length=128, label=_("New Password"))

    def validate_verification_code(self, value):
        if not (1000 <= value <= 9999):
            raise serializers.ValidationError(_("Verification code must be a 4-digit number."))
        return value

    def validate_new_password(self, value):
        validate_password(value)
        return value


class UserPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProgram
        fields = "__all__"


class LanguageUpdateSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=[('uz', 'Uzbek'), ('ru', 'Russian'), ('en', 'English')])


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email_or_phone', 'phone_or_email_optional', 'gender',
            'country', 'age', 'height', 'weight', 'goal', 'level',
            'is_premium', 'photo', 'language', 'date_joined', 'is_active'
        ]
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            'email_or_phone': {'required': False},
        }



class ReminderTimeSerializer(serializers.Serializer):
    reminder_time = serializers.CharField(
        required=True,
        help_text="Enter time in HH:MM format (24-hour format).",
        max_length=5
    )

    def validate_reminder_time(self, value):
        from datetime import datetime
        try:
            datetime.strptime(value, "%H:%M").time()
            return value
        except ValueError:
            raise serializers.ValidationError("Invalid time format. Use 'HH:MM' format.")


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email_or_phone', 'phone_or_email_optional', 'gender',
            'country', 'age', 'height', 'weight', 'goal', 'level',
            'is_premium', 'photo', 'language', 'date_joined', 'is_active', 'last_login'
        ]

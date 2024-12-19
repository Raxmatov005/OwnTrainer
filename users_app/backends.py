from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailOrPhoneBackend(BaseBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username:
            return None

        normalized_input = username.strip()

        user = User.objects.filter(email_or_phone__in=[normalized_input, f"+{normalized_input}"]).first()

        if user and user.check_password(password):
            return user

        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

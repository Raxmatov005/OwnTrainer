# click/serializers.py

from rest_framework import serializers
from users_app.models import UserProgram

class ClickOrderSerializer(serializers.ModelSerializer):
    subscription_type = serializers.ChoiceField(
        choices=UserProgram.SUBSCRIPTION_CHOICES,
        required=True
    )

    class Meta:
        model = UserProgram
        fields = ["subscription_type"]  # no direct "amount" field from user

    def create(self, validated_data):
        """
        Normally DRF uses this to create the model instance, but we will override
        in our view to set amount, start_date, end_date, etc.
        """
        return UserProgram.objects.create(**validated_data)

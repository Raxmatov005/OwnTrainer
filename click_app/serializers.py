# click/serializers.py

from rest_framework import serializers
from users_app.models import UserSubscription

class ClickOrderSerializer(serializers.ModelSerializer):
    subscription_type = serializers.ChoiceField(
        choices=UserSubscription._meta.get_field("subscription_type").choices,  # ✅ Correct field
        required=True
    )

    class Meta:
        model = UserSubscription
        fields = ["subscription_type"]  # no direct "amount" field from user

    def create(self, validated_data):
        """
        Normally DRF uses this to create the model instance, but we will override
        in our view to set amount, start_date, end_date, etc.
        """
        return UserSubscription.objects.create(**validated_data)

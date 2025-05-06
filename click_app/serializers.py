# click/serializers.py
from rest_framework import serializers
from users_app.models import UserSubscription

class ClickOrderSerializer(serializers.ModelSerializer):
    subscription_type = serializers.ChoiceField(
        choices=UserSubscription._meta.get_field("subscription_type").choices,
        required=True
    )

    class Meta:
        model = UserSubscription
        fields = ["subscription_type", "amount_in_soum", "is_active"]  # Include necessary fields
        extra_kwargs = {
            "amount_in_soum": {"required": False},  # Set by view
            "is_active": {"required": False},       # Set by view
        }

    def create(self, validated_data):
        """
        Create a UserSubscription instance with additional data set by the view.
        """
        user = self.context['request'].user
        subscription_type = validated_data['subscription_type']
        amount_in_soum = self.context.get('amount_in_soum', 0)  # Default to 0 if not provided
        from click_app.views import SUBSCRIPTION_COSTS
        amount_in_soum = SUBSCRIPTION_COSTS.get(subscription_type, 0)
        instance = UserSubscription.objects.create(
            user=user,
            subscription_type=subscription_type,
            amount_in_soum=amount_in_soum,
            is_active=False  # Set by view logic
        )
        return instance

    def update(self, instance, validated_data):
        instance.subscription_type = validated_data.get('subscription_type', instance.subscription_type)
        instance.amount_in_soum = validated_data.get('amount_in_soum', instance.amount_in_soum)
        instance.is_active = validated_data.get('is_active', instance.is_active)
        instance.save()
        return instance
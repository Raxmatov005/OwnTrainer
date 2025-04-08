from django.utils import timezone
from django.shortcuts import redirect, get_object_or_404
from rest_framework.generics import CreateAPIView
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from pyclick import PyClick
from pyclick.views import PyClickMerchantAPIView
from users_app.models import UserSubscription, UserProgram, SessionCompletion, MealCompletion, ExerciseBlockCompletion
from datetime import timedelta
from .serializers import ClickOrderSerializer
import logging

# Subscription pricing and durations
SUBSCRIPTION_COSTS = {
    'month': 10000,
    'quarter': 25000,
    'year': 90000
}
SUBSCRIPTION_DAYS = {
    'month': 30,
    'quarter': 90,
    'year': 365
}

logger = logging.getLogger(__name__)

class CreateClickOrderView(CreateAPIView):
    """
    Processes subscription payments via Click and creates a payment link.
    """
    serializer_class = ClickOrderSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        subscription_type = request.data.get('subscription_type')
        if subscription_type not in SUBSCRIPTION_COSTS:
            return Response(
                {"error": "Invalid subscription_type. Must be month, quarter, or year."},
                status=400
            )
        amount = SUBSCRIPTION_COSTS[subscription_type]
        add_days = SUBSCRIPTION_DAYS[subscription_type]
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "User must be logged in."}, status=401)

        user_subscription, created = UserSubscription.objects.get_or_create(
            user=user, is_active=True, defaults={"subscription_type": subscription_type}
        )
        user_subscription.subscription_type = subscription_type
        user_subscription.is_active = False  # Mark inactive until payment success
        user_subscription.save()

        return_url = 'https://owntrainer.uz/'
        pay_url = PyClick.generate_url(order_id=user_subscription.id, amount=str(amount), return_url=return_url)
        return redirect(pay_url)


class OrderCheckAndPayment(PyClick):
    """
    Handles Click payment verification and subscription updates.
    """

    def check_order(self, order_id: str, amount: str):
        try:
            subscription = UserSubscription.objects.get(id=order_id)
            if int(amount) == SUBSCRIPTION_COSTS[subscription.subscription_type]:
                return self.ORDER_FOUND
            return self.INVALID_AMOUNT
        except UserSubscription.DoesNotExist:
            return self.ORDER_NOT_FOUND

    def successfully_payment(self, order_id: str, transaction: object):
        """
        Called when Click confirms a successful payment.
        """
        try:
            user_subscription = UserSubscription.objects.get(id=order_id)
            logger.info(f"✅ Payment received for user {user_subscription.user.email_or_phone}")

            # Mark subscription as active and save it.
            user_subscription.is_active = True
            user_subscription.save()

            add_days = SUBSCRIPTION_DAYS[user_subscription.subscription_type]
            user_subscription.extend_subscription(add_days)
            logger.info(f"✅ Subscription extended for {user_subscription.user.email_or_phone} by {add_days} days")

            # Create sessions for the user using the new unified flow.
            self.create_sessions_for_user(user_subscription.user)

        except UserSubscription.DoesNotExist:
            logger.error(f"❌ No subscription found with ID: {order_id}")

    def handle_cancelled_payment(self, params, result, *args, **kwargs):
        transaction = PyClick.get_by_transaction_id(transaction_id=params["id"])
        user_subscription_id = transaction.order_id  # Use order_id instead of account.id
        try:
            user_subscription = UserSubscription.objects.get(id=user_subscription_id)
            user_subscription.is_active = False  # Ensure subscription remains inactive
            user_subscription.save()
            logger.info(f"✅ Cancelled payment for subscription ID: {user_subscription_id}")
        except UserSubscription.DoesNotExist:
            logger.error(f"❌ No subscription found with ID: {user_subscription_id}")



class OrderTestView(PyClickMerchantAPIView):
    VALIDATE_CLASS = OrderCheckAndPayment

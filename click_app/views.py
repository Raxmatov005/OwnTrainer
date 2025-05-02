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
    'month': 1000,
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

    def post(self, request, *args, **kwargs):
        logger.info(f"Click webhook payload: {request.body}")
        method = request.data.get("method")
        if not method:
            logger.error("Click webhook missing 'method' field")
            return Response({
                "error": {
                    "code": -32500,
                    "message": {"en": "Missing method"}
                }
            }, status=400)
        return super().post(request, *args, **kwargs)




class ClickPrepareAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logger.info(f"Click Prepare request received: {request.data}")
        try:
            order_id = request.data.get("order_id")
            amount = int(request.data.get("amount"))
            merchant_id = request.data.get("merchant_id")
            service_id = request.data.get("service_id")

            if not all([order_id, amount, merchant_id, service_id]):
                logger.error(f"Missing required parameters: {request.data}")
                return Response({"error": -1}, status=400)

            subscription = UserSubscription.objects.get(id=order_id)
            expected_amount = subscription.amount_in_soum * 100  # Convert to tiyins
            if amount != expected_amount:
                logger.warning(f"Amount mismatch: expected {expected_amount} tiyins, got {amount} tiyins")
                return Response({"error": -1}, status=400)

            if merchant_id != "9988*":  # Replace with your actual merchant ID
                logger.error(f"Invalid merchant_id: {merchant_id}")
                return Response({"error": -1}, status=400)

            logger.info(f"Prepare request validated successfully for order_id {order_id}")
            return Response({"error": 0}, status=200)
        except UserSubscription.DoesNotExist:
            logger.error(f"Subscription not found for order_id: {order_id}")
            return Response({"error": -1}, status=404)
        except ValueError as e:
            logger.error(f"Invalid amount format: {e}, data: {request.data}")
            return Response({"error": -1}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error in Click Prepare: {str(e)}, data: {request.data}")
            return Response({"error": -1}, status=500)


class ClickCompleteAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logger.info(f"Click Complete request: {request.data}")
        try:
            order_id = request.data.get("order_id")
            amount = int(request.data.get("amount"))
            status = request.data.get("state")  # Use 'state' instead of 'status' per Click docs

            subscription = UserSubscription.objects.get(id=order_id)
            expected_amount = subscription.amount_in_soum * 100
            if amount != expected_amount:
                logger.warning(f"Amount mismatch: expected {expected_amount} tiyins, got {amount} tiyins")
                return Response({"error": -1})

            if status == "1":  # Success status (confirm with Click docs)
                subscription.is_active = True
                add_days = SUBSCRIPTION_DAYS.get(subscription.subscription_type, 30)
                subscription.extend_subscription(add_days)
                subscription.save()
                logger.info(f"Click payment successful for subscription: {subscription.id}")
            elif status == "0":  # Failed status
                subscription.is_active = False
                subscription.save()
                logger.info(f"Click payment failed for subscription: {subscription.id}")
            else:
                logger.warning(f"Unknown state: {status}")
                return Response({"error": -1})

            return Response({"error": 0})
        except UserSubscription.DoesNotExist:
            logger.error(f"Subscription not found for order_id: {order_id}")
            return Response({"error": -1})
        except Exception as e:
            logger.error(f"Error in Click Complete: {str(e)}")
            return Response({"error": -1})


class HealthCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"}, status=200)
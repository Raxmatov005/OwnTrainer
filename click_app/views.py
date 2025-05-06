from django.utils import timezone
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from pyclick import PyClick
from pyclick.views import PyClickMerchantAPIView
from users_app.models import UserSubscription
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

class CreateClickOrderView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = ClickOrderSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        subscription_type = serializer.validated_data['subscription_type']
        amount = SUBSCRIPTION_COSTS[subscription_type]
        add_days = SUBSCRIPTION_DAYS[subscription_type]
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "User must be logged in."}, status=401)

        user_subscription, created = UserSubscription.objects.get_or_create(
            user=user,
            defaults={"subscription_type": subscription_type, "amount_in_soum": amount, "is_active": False}
        )
        user_subscription.subscription_type = subscription_type
        user_subscription.amount_in_soum = amount
        user_subscription.is_active = False
        user_subscription.save()

        return_url = 'https://owntrainer.uz/'
        amount_in_tiyins = amount * 100
        logger.info(f"Generating Click URL with amount: {amount_in_tiyins} tiyins")
        pay_url = PyClick.generate_url(order_id=user_subscription.id, amount=str(amount_in_tiyins), return_url=return_url)
        logger.info(f"Generated Click URL: {pay_url}")
        return redirect(pay_url)

class OrderCheckAndPayment(PyClick):
    def check_order(self, order_id: str, amount: str):
        try:
            subscription = UserSubscription.objects.get(id=order_id)
            expected_amount = subscription.amount_in_soum * 100  # Convert to tiyins
            if int(amount) == expected_amount:
                return self.ORDER_FOUND
            return self.INVALID_AMOUNT
        except UserSubscription.DoesNotExist:
            return self.ORDER_NOT_FOUND

    def successfully_payment(self, order_id: str, transaction: object):
        try:
            user_subscription = UserSubscription.objects.get(id=order_id)
            logger.info(f"✅ Payment received for user {user_subscription.user.email_or_phone}")
            add_days = SUBSCRIPTION_DAYS[user_subscription.subscription_type]
            user_subscription.extend_subscription(add_days)
            logger.info(f"✅ Subscription extended for {user_subscription.user.email_or_phone} by {add_days} days")
            # Assuming create_sessions_for_user is defined elsewhere
            from users_app.views import create_sessions_for_user
            create_sessions_for_user(user_subscription.user)
            PyClick.confirm_transaction(transaction.transaction_id)
        except UserSubscription.DoesNotExist:
            logger.error(f"❌ No subscription found with ID: {order_id}")

    def handle_cancelled_payment(self, params, result, *args, **kwargs):
        transaction = PyClick.get_by_transaction_id(transaction_id=params["id"])
        user_subscription_id = transaction.order_id
        try:
            user_subscription = UserSubscription.objects.get(id=user_subscription_id)
            user_subscription.is_active = False
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
    parser_classes = [FormParser, MultiPartParser]

    def post(self, request):
        logger.info(f"Click Prepare request at {timezone.now()}: Data={request.data}, Headers={request.headers}, Method={request.method}, IP={request.META.get('REMOTE_ADDR')}")
        try:
            # Map Click API fields to expected parameters
            order_id = request.data.get("merchant_trans_id")  # Click uses merchant_trans_id for order_id
            amount = request.data.get("amount")
            merchant_id = request.data.get("merchant_id")  # May be missing; handle fallback
            service_id = request.data.get("service_id")

            # Fallback for merchant_id if not provided (e.g., hardcoded or from config)
            if not merchant_id:
                merchant_id = "31383"  # Hardcoded based on your logs; replace with config if possible

            if not all([order_id, amount, merchant_id, service_id]):
                logger.error(f"Missing required parameters: {request.data}")
                return Response({"error": -1}, status=400)

            # Ensure we handle the first element if it's a list (from QueryDict)
            order_id = order_id[0] if isinstance(order_id, list) else order_id
            amount = amount[0] if isinstance(amount, list) else amount
            merchant_id = merchant_id[0] if isinstance(merchant_id, list) else merchant_id
            service_id = service_id[0] if isinstance(service_id, list) else service_id

            try:
                amount = int(amount)  # Amount should already be in tiyins
            except ValueError:
                logger.error(f"Invalid amount format: {amount}, data: {request.data}")
                return Response({"error": -1}, status=400)

            try:
                subscription = UserSubscription.objects.get(id=order_id)
                expected_amount = subscription.amount_in_soum * 100  # Convert so'm to tiyins
                logger.debug(f"Expected amount: {expected_amount} tiyins, received: {amount} tiyins")
                if amount != expected_amount:
                    logger.warning(f"Amount mismatch: expected {expected_amount} tiyins, got {amount} tiyins")
                    return Response({"error": -1}, status=400)
            except UserSubscription.DoesNotExist:
                logger.error(f"Subscription not found for order_id: {order_id}")
                return Response({"error": -1}, status=404)

            if merchant_id != "31383":
                logger.error(f"Invalid merchant_id: {merchant_id}")
                return Response({"error": -1}, status=400)

            logger.info(f"Prepare request validated successfully for order_id {order_id}")
            return Response({"error": 0}, status=200)
        except Exception as e:
            logger.error(f"Unexpected error in Click Prepare: {str(e)}, data: {request.data}", exc_info=True)
            return Response({"error": -1}, status=500)

class ClickCompleteAPIView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [FormParser, MultiPartParser]

    def post(self, request):
        logger.info(f"Click Complete request at {timezone.now()}: Data={request.data}, Headers={request.headers}, Method={request.method}, IP={request.META.get('REMOTE_ADDR')}")
        try:
            order_id = request.data.get("order_id")
            amount = request.data.get("amount")
            state = request.data.get("state")
            logger.debug(f"Received amount: {amount}")

            if not all([order_id, amount, state]):
                logger.error(f"Missing required parameters: {request.data}")
                return Response({"result": {"_ALPHABET_": -1}}, status=400)

            order_id = order_id[0] if isinstance(order_id, list) else order_id
            amount = amount[0] if isinstance(amount, list) else amount
            state = state[0] if isinstance(state, list) else state

            try:
                amount = int(amount)
                state = int(state)
            except ValueError:
                logger.error(f"Invalid amount or state format: amount={amount}, state={state}, data: {request.data}")
                return Response({"result": {"_ALPHABET_": -1}}, status=400)

            try:
                subscription = UserSubscription.objects.get(id=order_id)
                expected_amount = subscription.amount_in_soum * 100
                logger.debug(f"Expected amount: {expected_amount} tiyins, received: {amount} tiyins")
                if amount != expected_amount:
                    logger.warning(f"Amount mismatch: expected {expected_amount} tiyins, got {amount} tiyins")
                    return Response({"result": {"_ALPHABET_": -1}}, status=400)
            except UserSubscription.DoesNotExist:
                logger.error(f"Subscription not found for order_id: {order_id}")
                return Response({"result": {"_ALPHABET_": -1}}, status=404)

            if state == 1:
                subscription.is_active = True
                add_days = SUBSCRIPTION_DAYS.get(subscription.subscription_type, 30)
                subscription.extend_subscription(add_days)
                subscription.save()
                logger.info(f"✅ Click payment successful for subscription ID: {order_id}")
            elif state == 0:
                subscription.is_active = False
                subscription.save(update_fields=['is_active'])
                logger.info(f"❌ Click payment failed for subscription ID: {order_id}")
            else:
                logger.warning(f"Unknown state: {state}")
                return Response({"result": {"_ALPHABET_": -1}}, status=400)

            return Response({"result": {"_ALPHABET_": 0}}, status=200)
        except Exception as e:
            logger.error(f"Error in Click Complete: {str(e)}, data: {request.data}", exc_info=True)
            return Response({"result": {"_ALPHABET_": -1}}, status=500)

class HealthCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"}, status=200)
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
import hashlib
import logging
import requests
import time
from register import settings



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
            expected_amount = subscription.amount_in_soum  # Convert to tiyins
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
        logger.info(
            f"Click Prepare request at {timezone.now()}: Data={request.data}, Headers={request.headers}, Method={request.method}, IP={request.META.get('REMOTE_ADDR')}")
        try:
            click_trans_id = request.data.get("click_trans_id")
            service_id = request.data.get("service_id")
            click_paydoc_id = request.data.get("click_paydoc_id")
            order_id = request.data.get("merchant_trans_id")
            merchant_prepare_id = request.data.get("merchant_prepare_id", click_paydoc_id)
            amount = request.data.get("amount")
            action = request.data.get("action")
            sign_time = request.data.get("sign_time")
            sign_string = request.data.get("sign_string")

            required_params = [click_trans_id, service_id, click_paydoc_id, order_id, amount, action, sign_time,
                               sign_string]
            if not all(required_params):
                logger.error(f"Missing required parameters: {request.data}")
                return Response({"error": -1}, status=400)

            # Ensure params are not lists if they were parsed as such
            click_trans_id = click_trans_id if isinstance(click_trans_id, list) else click_trans_id
            service_id = service_id if isinstance(service_id, list) else service_id
            click_paydoc_id = click_paydoc_id if isinstance(click_paydoc_id, list) else click_paydoc_id
            order_id = order_id if isinstance(order_id, list) else order_id
            merchant_prepare_id = merchant_prepare_id if isinstance(merchant_prepare_id, list) else merchant_prepare_id
            amount = amount if isinstance(amount, list) else amount
            action = action if isinstance(action, list) else action
            sign_time = sign_time if isinstance(sign_time, list) else sign_time
            sign_string = sign_string if isinstance(sign_string, list) else sign_string

            # Log all parameters for debugging
            logger.info(f"click_trans_id: {click_trans_id}")
            logger.info(f"service_id: {service_id}")
            logger.info(f"merchant_prepare_id: {merchant_prepare_id}")
            logger.info(f"click_paydoc_id: {click_paydoc_id}")
            logger.info(f"order_id: {order_id}")
            logger.info(f"amount: {amount}")
            logger.info(f"action: {action}")
            logger.info(f"sign_time: {sign_time}")

            # Validate sign_string as per Click support's instruction
            secret_key = settings.CLICK_SETTINGS['secret_key']
            logger.info(f"Using secret_key: {secret_key}")

            # Adjust sign_input based on action: exclude merchant_prepare_id for action=0
            if action == '0':
                sign_input = f"{click_trans_id}{service_id}{secret_key}{order_id}{amount}{action}{sign_time}"
            else:
                sign_input = f"{click_trans_id}{service_id}{secret_key}{order_id}{merchant_prepare_id}{amount}{action}{sign_time}"

            logger.info(f"Sign input: {sign_input}")
            expected_sign = hashlib.md5(sign_input.encode()).hexdigest()
            logger.info(f"Expected sign: {expected_sign}, Received sign: {sign_string}")

            if sign_string.lower() != expected_sign.lower():
                logger.error(f"Invalid sign_string: expected {expected_sign}, got {sign_string}")
                return Response({"error": -4}, status=400)

            try:
                amount = int(amount)
            except ValueError:
                logger.error(f"Invalid amount format: {amount}, data: {request.data}")
                return Response({"error": -1}, status=400)

            try:
                subscription = UserSubscription.objects.get(id=order_id)
                expected_amount = subscription.amount_in_soum
                logger.debug(f"Expected amount: {expected_amount} tiyins, received: {amount} tiyins")

                if amount != expected_amount:
                    logger.warning(f"Amount mismatch: expected {expected_amount} tiyins, got {amount} tiyins")
                    return Response({"error": -1}, status=400)
            except UserSubscription.DoesNotExist:
                logger.error(f"Subscription not found for order_id: {order_id}")
                return Response({"error": -1}, status=404)

            if str(service_id) != str(settings.CLICK_SETTINGS['service_id']):
                logger.error(f"Invalid service_id: {service_id}")
                return Response({"error": -1}, status=400)

            logger.info(f"Prepare request validated successfully for order_id {order_id}")
            return Response({"error": 0, "merchant_prepare_id": merchant_prepare_id}, status=200)

        except Exception as e:
            logger.error(f"Unexpected error in Click Prepare: {str(e)}, data: {request.data}", exc_info=True)
            return Response({"error": -1}, status=500)


class ClickCompleteAPIView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [FormParser, MultiPartParser]

    class ClickCompleteAPIView(APIView):
        permission_classes = [AllowAny]
        parser_classes = [FormParser, MultiPartParser]

        def post(self, request):
            logger.info(f"Click Complete request at {timezone.now()}: Data={request.data}")
            try:
                click_trans_id = request.data.get("click_trans_id")
                service_id = request.data.get("service_id")
                click_paydoc_id = request.data.get("click_paydoc_id")
                order_id = request.data.get("merchant_trans_id")
                merchant_prepare_id = request.data.get("merchant_prepare_id", click_paydoc_id)
                amount = request.data.get("amount")
                state = request.data.get("error")
                action = request.data.get("action")
                sign_time = request.data.get("sign_time")
                sign_string = request.data.get("sign_string")

                required_params = [click_trans_id, service_id, click_paydoc_id, order_id, amount, state, action,
                                   sign_time, sign_string]
                if not all(required_params):
                    logger.error(f"Missing required parameters: {request.data}")
                    return Response({"error": -1}, status=400)

                # Handle list parameters
                click_trans_id = click_trans_id[0] if isinstance(click_trans_id, list) else click_trans_id
                service_id = service_id[0] if isinstance(service_id, list) else service_id
                click_paydoc_id = click_paydoc_id[0] if isinstance(click_paydoc_id, list) else click_paydoc_id
                order_id = order_id[0] if isinstance(order_id, list) else order_id
                merchant_prepare_id = merchant_prepare_id[0] if isinstance(merchant_prepare_id,
                                                                           list) else merchant_prepare_id
                amount = amount[0] if isinstance(amount, list) else amount
                state = state[0] if isinstance(state, list) else state
                action = action[0] if isinstance(action, list) else action
                sign_time = sign_time[0] if isinstance(sign_time, list) else sign_time
                sign_string = sign_string[0] if isinstance(sign_string, list) else sign_string

                logger.info(
                    f"Click params: click_trans_id={click_trans_id}, service_id={service_id}, "
                    f"order_id={order_id}, amount={amount}, state={state}, action={action}, sign_time={sign_time}"
                )

                # Validate sign_string
                secret_key = settings.CLICK_SETTINGS['secret_key']
                sign_input = f"{click_trans_id}{service_id}{secret_key}{order_id}{merchant_prepare_id}{amount}{action}{sign_time}"
                expected_sign = hashlib.md5(sign_input.encode()).hexdigest()
                logger.info(f"Sign input: {sign_input}")
                logger.info(f"Expected sign: {expected_sign}, Received sign: {sign_string}")
                if sign_string != expected_sign:
                    logger.error(f"Invalid sign_string: expected {expected_sign}, got {sign_string}")
                    # Log alternative sign_input for debugging
                    alt_sign_input = f"{click_trans_id}{service_id}{secret_key}{order_id}{amount}{action}{sign_time}"
                    alt_expected_sign = hashlib.md5(alt_sign_input.encode()).hexdigest()
                    logger.info(f"Alternative sign input (no merchant_prepare_id): {alt_sign_input}")
                    logger.info(f"Alternative expected sign: {alt_expected_sign}")
                    return Response({"error": -4}, status=400)

                try:
                    amount = int(amount)
                    state = int(state)
                except ValueError:
                    logger.error(f"Invalid amount or state format: amount={amount}, state={state}")
                    return Response({"error": -1}, status=400)

                try:
                    subscription = UserSubscription.objects.get(id=order_id)
                    expected_amount = subscription.amount_in_soum
                    logger.info(
                        f"Subscription ID: {order_id}, amount_in_soum: {subscription.amount_in_soum}, "
                        f"is_active: {subscription.is_active}, start_date: {subscription.start_date}, "
                        f"end_date: {subscription.end_date}"
                    )
                    if amount != expected_amount:
                        logger.warning(f"Amount mismatch: expected {expected_amount} soums, got {amount} soums")
                        return Response({"error": -1}, status=400)
                except UserSubscription.DoesNotExist:
                    logger.error(f"Subscription not found for order_id: {order_id}")
                    return Response({"error": -1}, status=404)

                if str(service_id) != str(settings.CLICK_SETTINGS['service_id']):
                    logger.error(f"Invalid service_id: {service_id}")
                    return Response({"error": -1}, status=400)

                logger.info(f"Processing Click payment for subscription ID: {order_id}, state: {state}")
                if state == 0:
                    merchant_user_id = settings.CLICK_SETTINGS['merchant_user_id']
                    secret_key = settings.CLICK_SETTINGS['secret_key']
                    timestamp = str(int(time.time()))
                    digest = hashlib.sha1((timestamp + secret_key).encode()).hexdigest()
                    auth_header = f"{merchant_user_id}:{digest}:{timestamp}"

                    confirm_url = "https://api.click.uz/v2/merchant/click_pass/confirm"
                    confirm_payload = {
                        "service_id": settings.CLICK_SETTINGS['service_id'],
                        "payment_id": click_trans_id
                    }
                    confirm_headers = {
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "Auth": auth_header
                    }

                    response = requests.post(confirm_url, json=confirm_payload, headers=confirm_headers)
                    logger.info(f"Click API confirm response: status={response.status_code}, body={response.text}")
                    if response.status_code == 200 and response.json().get("error_code") == 0:
                        logger.info(f"✅ Payment confirmed with Click API for transaction {click_trans_id}")
                        subscription.is_active = True
                        add_days = SUBSCRIPTION_DAYS.get(subscription.subscription_type, 30)
                        subscription.extend_subscription(add_days)
                        try:
                            subscription.save(update_fields=['start_date', 'end_date', 'is_active'])
                            logger.info(
                                f"✅ Click payment successful for subscription ID: {order_id}, "
                                f"is_active: {subscription.is_active}, end_date: {subscription.end_date}"
                            )
                        except Exception as e:
                            logger.error(f"❌ Failed to save subscription for ID: {order_id}, error: {str(e)}")
                            return Response({"error": -1}, status=500)
                        from users_app.views import create_sessions_for_user
                        create_sessions_for_user(subscription.user)
                    else:
                        logger.error(
                            f"❌ Failed to confirm payment with Click API: status={response.status_code}, body={response.text}")
                        return Response({"error": -1}, status=400)
                elif state < 0:
                    subscription.is_active = False
                    subscription.save(update_fields=['is_active'])
                    logger.info(f"❌ Click payment failed for subscription ID: {order_id}, state: {state}")
                else:
                    logger.warning(f"Unknown state/error: {state}")
                    return Response({"error": -1}, status=400)

                return Response({"error": 0}, status=200)
            except Exception as e:
                logger.error(f"Error in Click Complete: {str(e)}, data: {request.data}", exc_info=True)
                return Response({"error": -1}, status=500)

class HealthCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"}, status=200)
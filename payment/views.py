from payme.types import response
from payme.views import PaymeWebHookAPIView
from payme.models import PaymeTransactions
from users_app.models import UserSubscription
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from click_app.views import SUBSCRIPTION_COSTS, PyClick
from .utils import generate_payme_docs_style_url


# Subscription duration mapping
SUBSCRIPTION_DAYS = {
    'month': 30,
    'quarter': 90,
    'year': 365
}

import logging

logger = logging.getLogger(__name__)

class PaymeCallBackAPIView(PaymeWebHookAPIView):
    def check_perform_transaction(self, params):
        logger.info(f"Payme check_perform_transaction params: {params}")
        try:
            subscription = UserSubscription.objects.get(id=params.get('account', {}).get('id'))
            amount = int(params.get('amount'))
            expected_amount = subscription.amount

            logger.info(
                f"Checking amount: Payme sent {amount} tiyins, expected {expected_amount} tiyins for subscription_type {subscription.subscription_type}")
            if amount != expected_amount:
                logger.warning(f"Amount mismatch: expected {expected_amount} tiyins, got {amount} tiyins")
                return response.CheckPerformTransaction(
                    allow=False,
                ).as_resp()

            logger.info("Transaction allowed")
            return response.CheckPerformTransaction(allow=True).as_resp()
        except UserSubscription.DoesNotExist:
            logger.error("Invalid subscription ID")
            return response.CheckPerformTransaction(
                allow=False,
                reason=-31050,
                message="Invalid subscription ID",
                data="account[id]"
            ).as_resp()
        except Exception as e:
            logger.error(f"Error in check_perform_transaction: {str(e)}")
            return response.CheckPerformTransaction(
                allow=False,
            ).as_resp()

    def handle_successfully_payment(self, params, result, *args, **kwargs):
        logger.info(f"Payme handle_successfully_payment params: {params}")
        transaction = PaymeTransactions.get_by_transaction_id(transaction_id=params["id"])
        subscription_id = transaction.account.id
        try:
            subscription = UserSubscription.objects.get(id=subscription_id)
            subscription.is_active = True
            add_days = SUBSCRIPTION_DAYS.get(subscription.subscription_type, 30)
            subscription.extend_subscription(add_days)
            subscription.save()
            logger.info(f"✅ Payment successful for subscription ID: {subscription_id}")
        except UserSubscription.DoesNotExist:
            logger.error(f"❌ No subscription found with ID: {subscription_id}")

    def handle_cancelled_payment(self, params, result, *args, **kwargs):
        logger.info(f"Payme handle_cancelled_payment params: {params}")
        transaction = PaymeTransactions.get_by_transaction_id(transaction_id=params["id"])
        subscription_id = transaction.account.id
        try:
            subscription = UserSubscription.objects.get(id=subscription_id)
            subscription.is_active = False
            subscription.save()
            logger.info(f"✅ Cancelled payment for subscription ID: {subscription_id}")
        except UserSubscription.DoesNotExist:
            logger.error(f"❌ No subscription found with ID: {subscription_id}")

class UnifiedPaymentInitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_method = request.data.get("payment_method")
        subscription_type = request.data.get("subscription_type")

        if subscription_type not in SUBSCRIPTION_COSTS:
            return Response({"error": "Invalid subscription_type"}, status=400)

        if payment_method not in ["click", "payme"]:
            return Response({"error": "Invalid payment_method"}, status=400)

        user = request.user
        amount = SUBSCRIPTION_COSTS[subscription_type]
        logger.info(
            f"Creating subscription for user {user.email_or_phone} with type {subscription_type}, amount {amount} so'm")

        subscription, created = UserSubscription.objects.get_or_create(
            user=user,
            is_active=True,
            defaults={"subscription_type": subscription_type, "amount_in_soum": amount}
        )
        # Debug and enforce consistency
        if subscription.amount_in_soum != amount:
            logger.warning(
                f"Consistency check failed: amount_in_soum was {subscription.amount_in_soum}, setting to {amount}")
        subscription.subscription_type = subscription_type
        subscription.amount_in_soum = amount
        subscription.is_active = False
        subscription.save()

        if payment_method == "payme":
            payme_url = generate_payme_docs_style_url(
                subscription_type=subscription_type,
                user_program_id=subscription.id
            )
            logger.info(f"Payme redirect URL: {payme_url}")
            return Response({"redirect_url": payme_url})

        elif payment_method == "click":
            return_url = "https://owntrainer.uz/payment/success"
            pay_url = PyClick.generate_url(
                order_id=str(subscription.id),
                amount=str(amount),
                return_url=return_url
            )
            logger.info(f"Click redirect URL: {pay_url}, Request data: {request.data}")
            return Response({"redirect_url": pay_url})

        return Response({"error": "Unhandled payment method"}, status=500)
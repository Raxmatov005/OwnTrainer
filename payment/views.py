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

class PaymeCallBackAPIView(PaymeWebHookAPIView):
    """
    Handles Payme Webhook API calls for subscription.
    """

    def check_perform_transaction(self, params):
        try:
            # Fetch UserSubscription instead of UserProgram
            subscription = UserSubscription.objects.get(id=params.get('account', {}).get('id'))
            amount = int(params.get('amount'))
            expected_amount = SUBSCRIPTION_COSTS[subscription.subscription_type]

            if amount != expected_amount:
                return response.CheckPerformTransaction(
                    allow=False,
                ).as_resp()

            return response.CheckPerformTransaction(allow=True).as_resp()

        except UserSubscription.DoesNotExist:
            return response.CheckPerformTransaction(
                allow=False,
                reason=-31050,
                message="Invalid subscription ID",
                data="account[id]"
            ).as_resp()

        except Exception as e:
            return response.CheckPerformTransaction(
                allow=False,
            ).as_resp()

    def handle_successfully_payment(self, params, result, *args, **kwargs):
        transaction = PaymeTransactions.get_by_transaction_id(transaction_id=params["id"])
        subscription_id = transaction.account.id
        try:
            subscription = UserSubscription.objects.get(id=subscription_id)
            subscription.is_active = True
            add_days = SUBSCRIPTION_DAYS.get(subscription.subscription_type, 30)
            subscription.extend_subscription(add_days)
            subscription.save()
            print(f"✅ Payment successful for subscription ID: {subscription_id}")
        except UserSubscription.DoesNotExist:
            print(f"❌ No subscription found with ID: {subscription_id}")

    def handle_cancelled_payment(self, params, result, *args, **kwargs):
        """
        Handles canceled payments by ensuring the subscription remains unaffected.
        """
        transaction = PaymeTransactions.get_by_transaction_id(transaction_id=params["id"])
        subscription_id = transaction.account.id
        try:
            subscription = UserSubscription.objects.get(id=subscription_id)
            subscription.is_active = False
            subscription.save()
            print(f"✅ Cancelled payment for subscription ID: {subscription_id}")
        except UserSubscription.DoesNotExist:
            print(f"❌ No subscription found with ID: {subscription_id}")

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

        # Update or create subscription object
        subscription, _ = UserSubscription.objects.get_or_create(
            user=user,
            is_active=True,
            defaults={"subscription_type": subscription_type}
        )
        subscription.subscription_type = subscription_type
        subscription.is_active = False  # Set to True only after successful payment
        subscription.save()

        if payment_method == "click":
            return_url = "https://owntrainer.uz/payment/success"
            pay_url = PyClick.generate_url(
                order_id=subscription.id,
                amount=str(amount),
                return_url=return_url
            )
            return Response({"redirect_url": pay_url})

        elif payment_method == "payme":
            payme_url = generate_payme_docs_style_url(
                subscription_type=subscription_type,
                user_program_id=subscription.id  # Use subscription.id instead of user_program_id
            )
            return Response({"redirect_url": payme_url})

        return Response({"error": "Unhandled payment method"}, status=500)
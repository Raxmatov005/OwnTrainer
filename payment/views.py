from payme.types import response
from payme.views import PaymeWebHookAPIView
from payme.models import PaymeTransactions
from users_app.models import UserSubscription
from django.utils import timezone
from datetime import timedelta
from rest_framework.response import Response
from click_app.views import SUBSCRIPTION_DAYS, SUBSCRIPTION_COSTS, PyClick
from .utils import generate_payme_docs_style_url
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
import logging


logger = logging.getLogger(__name__)

class PaymeCallBackAPIView(PaymeWebHookAPIView):
    def check_perform_transaction(self, params):
        logger.info(f"Payme check_perform_transaction params: {params}")
        try:
            subscription_id = params.get('account', {}).get('id')
            if not subscription_id:
                logger.error("Missing subscription ID in account")
                return response.Error(
                    code=-31050,
                    message="Invalid subscription ID",
                    data="account[id]"
                ).as_resp()

            subscription = UserSubscription.objects.get(id=subscription_id)
            amount = int(params.get('amount'))
            expected_amount = subscription.amount_in_soum  # Ensure tiyins conversion

            logger.info(
                f"Checking amount: Payme sent {amount} tiyins, expected {expected_amount} tiyins for subscription_type {subscription.subscription_type}"
            )
            if amount != expected_amount:
                logger.warning(f"Amount mismatch: expected {expected_amount} tiyins, got {amount} tiyins")
                return response.Error(
                    code=-31001,
                    message="Amount mismatch",
                    data="amount"
                ).as_resp()

            logger.info("Transaction allowed")
            return response.CheckPerformTransaction(allow=True).as_resp()
        except UserSubscription.DoesNotExist:
            logger.error(f"Invalid subscription ID: {subscription_id}")
            return response.Error(
                code=-31050,
                message="Invalid subscription ID",
                data="account[id]"
            ).as_resp()
        except Exception as e:
            logger.error(f"Error in check_perform_transaction: {str(e)}")
            return response.Error(
                code=-31000,
                message="Internal server error",
                data=str(e)
            ).as_resp()

    def handle_successfully_payment(self, params, result, *args, **kwargs):
        logger.info(f"Payme handle_successfully_payment params: {params}")
        transaction = PaymeTransactions.get_by_transaction_id(transaction_id=params["id"])
        subscription_id = transaction.account.id
        try:
            subscription = UserSubscription.objects.get(id=subscription_id)
            add_days = SUBSCRIPTION_DAYS.get(subscription.subscription_type, 30)
            subscription.extend_subscription(add_days)
            subscription.is_active = True  # Explicitly set is_active
            subscription.save()
            logger.info(f"✅ Payment successful for subscription ID: {subscription_id}")
            # Assuming create_sessions_for_user is defined elsewhere
            from users_app.views import create_sessions_for_user
            create_sessions_for_user(subscription.user)
        except UserSubscription.DoesNotExist:
            logger.error(f"❌ No subscription found with ID: {subscription_id}")
        except Exception as e:
            logger.error(f"Error in handle_successfully_payment: {str(e)}")

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
        except Exception as e:
            logger.error(f"Error in handle_cancelled_payment: {str(e)}")





class UnifiedPaymentInitView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logger.info(f"User in /init/: {request.user}, Authenticated: {request.user.is_authenticated}")
        payment_method = request.data.get("payment_method")
        subscription_type = request.data.get("subscription_type")

        if subscription_type not in SUBSCRIPTION_COSTS:
            return Response({"error": "Invalid subscription_type"}, status=400)

        if payment_method not in ["click", "payme"]:
            return Response({"error": "Invalid payment_method"}, status=400)

        user = request.user
        amount = SUBSCRIPTION_COSTS[subscription_type]
        logger.info(f"Creating subscription for user {user.email_or_phone} with type {subscription_type}, amount {amount} so'm")


        subscription = UserSubscription.objects.create(
            user=user,
            subscription_type=subscription_type,
            amount_in_soum=amount,
            is_active=False,
            start_date=timezone.now().date()
        )
        logger.info(f"Created new subscription ID: {subscription.id} for user {user.email_or_phone}")


        if payment_method == "payme":
            payme_url = generate_payme_docs_style_url(
                subscription_type=subscription_type,
                user_program_id=subscription.id
            )
            logger.info(f"Payme redirect URL: {payme_url}")

            return Response({"redirect_url": payme_url})

        elif payment_method == "click":
            return_url = "https://owntrainer.uz/payment/success"
            amount_in_tiyins = amount
            pay_url = PyClick.generate_url(
                order_id=str(subscription.id),
                amount=str(amount_in_tiyins),
                return_url=return_url
            )
            logger.info(f"Click redirect URL: {pay_url}, Request data: {request.data}")
            return Response({"redirect_url": pay_url})

        return Response({"error": "Unhandled payment method"}, status=500)
from payme.types import response
from payme.views import PaymeWebHookAPIView
from payme.models import PaymeTransactions
from users_app.models import UserSubscription
from django.utils import timezone
from datetime import timedelta
from rest_framework.response import Response
from click_app.views import SUBSCRIPTION_DAYS, SUBSCRIPTION_COSTS
from .utils import generate_payme_docs_style_url
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
import logging
from pyclick import PyClick

logger = logging.getLogger(__name__)


class PaymeCallBackAPIView(PaymeWebHookAPIView):
    def check_perform_transaction(self, params):
        logger.info(f"Payme check_perform_transaction params: {params}")
        try:
            subscription_id = params.get('account', {}).get('id')
            if not subscription_id:
                logger.error("Missing subscription ID in account")
                return response.CheckPerformTransaction(
                    allow=False,
                ).as_resp()

            subscription = UserSubscription.objects.get(id=subscription_id)
            amount = int(params.get('amount'))
            expected_amount = subscription.amount_in_soum # Convert to tiyins

            logger.info(
                f"Checking amount: Payme sent {amount} tiyins, expected {expected_amount} tiyins for subscription_type {subscription.subscription_type}, subscription ID: {subscription_id}"
            )
            if amount != expected_amount:
                logger.warning(f"Amount mismatch: expected {expected_amount} tiyins, got {amount} tiyins")
                return response.CheckPerformTransaction(
                    allow=False,
                ).as_resp()

            logger.info(f"Transaction allowed for subscription ID: {subscription_id}")
            return response.CheckPerformTransaction(allow=True).as_resp()
        except UserSubscription.DoesNotExist:
            logger.error(f"Invalid subscription ID: {subscription_id}")
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
            # Deactivate other active subscriptions
            UserSubscription.objects.filter(
                user=subscription.user,
                is_active=True
            ).exclude(id=subscription.id).update(is_active=False, end_date=None)

            add_days = SUBSCRIPTION_DAYS.get(subscription.pending_extension_type or subscription.subscription_type, 30)
            if subscription.is_active and subscription.end_date:
                subscription.end_date = subscription.end_date + timedelta(days=add_days)
                subscription.pending_extension_type = None
                subscription.save(update_fields=['end_date', 'pending_extension_type'])
                logger.info(
                    f"✅ Extended active subscription ID: {subscription_id}, "
                    f"new end_date: {subscription.end_date}"
                )
            else:
                subscription.extend_subscription(add_days)
                subscription.is_active = True
                subscription.pending_extension_type = None
                subscription.save(update_fields=['start_date', 'end_date', 'is_active', 'pending_extension_type'])
                logger.info(
                    f"✅ Activated subscription ID: {subscription_id}, "
                    f"is_active: {subscription.is_active}, end_date: {subscription.end_date}"
                )
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
            subscription.pending_extension_type = None
            subscription.save(update_fields=['is_active', 'pending_extension_type'])
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
        if not user.is_authenticated:
            return Response({"error": "User must be logged in."}, status=401)

        amount = SUBSCRIPTION_COSTS[subscription_type]
        logger.info(
            f"Processing subscription for user {user.email_or_phone} with type {subscription_type}, amount {amount} so'm")

        # Find or create a subscription
        subscription = UserSubscription.objects.filter(
            user=user,
            is_active=True
        ).order_by('-end_date', '-id').first()

        if subscription:
            logger.info(
                f"Found active subscription ID: {subscription.id} for user {user.email_or_phone}, will extend duration")
            subscription.amount_in_soum = amount
            subscription.pending_extension_type = subscription_type
            subscription.save(update_fields=['amount_in_soum', 'pending_extension_type'])
        else:
            # Look for a pending subscription
            subscription = UserSubscription.objects.filter(
                user=user,
                subscription_type=subscription_type,
                is_active=False,
                end_date__isnull=True
            ).order_by('-start_date', '-id').first()

            if subscription:
                logger.info(f"Found pending subscription ID: {subscription.id} for user {user.email_or_phone}")
                subscription.amount_in_soum = amount
                subscription.start_date = timezone.now().date()
                subscription.pending_extension_type = subscription_type
                subscription.save(update_fields=['amount_in_soum', 'start_date', 'pending_extension_type'])
            else:
                subscription = UserSubscription.objects.create(
                    user=user,
                    subscription_type=subscription_type,
                    amount_in_soum=amount,
                    is_active=False,
                    start_date=timezone.now().date(),
                    end_date=None,
                    pending_extension_type=subscription_type
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
            return_url = "https://owntrainer.uz/payment-success"
            amount_in_tiyins = amount  # Convert so'm to tiyins
            pay_url = PyClick.generate_url(
                order_id=str(subscription.id),
                amount=str(amount_in_tiyins),
                return_url=return_url
            )
            logger.info(f"Click redirect URL: {pay_url}, Request data: {request.data}")
            return Response({"redirect_url": pay_url})

        return Response({"error": "Unhandled payment method"}, status=500)
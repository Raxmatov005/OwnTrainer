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
from django.conf import settings

logger = logging.getLogger(__name__)

class PaymeCallBackAPIView(PaymeWebHookAPIView):
    def dispatch_method(self, method, params):
        if method == "CreateTransaction":
            check_result = self.check_perform_transaction(params)
            if "error" in check_result:
                logger.info(f"CheckPerformTransaction failed for CreateTransaction: {check_result}")
                return check_result
            return self.create_transaction(params)
        return super().dispatch_method(method, params)

    def check_perform_transaction(self, params):
        logger.info(f"Payme check_perform_transaction full params: {params}")
        try:
            transaction_id = params.get('id')
            account_id = params.get('account', {}).get('id')
            amount = int(params.get('amount'))

            if not account_id:
                logger.error(f"Missing account ID in params: {params}")
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -31050,
                        "message": "Missing account ID",
                        "data": "account[id]"
                    },
                    "id": params.get('id', 0)
                }

            if not account_id.isdigit():
                logger.error(f"Invalid account ID format: {account_id}")
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -31050,
                        "message": "Invalid account ID format",
                        "data": "account[id]"
                    },
                    "id": params.get('id', 0)
                }

            try:
                subscription = UserSubscription.objects.get(id=int(account_id))
            except UserSubscription.DoesNotExist:
                logger.error(f"Invalid subscription ID: {account_id}")
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -31050,
                        "message": "Invalid subscription ID",
                        "data": "account[id]"
                    },
                    "id": params.get('id', 0)
                }

            expected_amount = subscription.amount_in_soum * 100
            logger.info(f"Subscription amount_in_soum: {subscription.amount_in_soum}, Expected tiyins: {expected_amount}")

            if amount != expected_amount:
                logger.warning(f"Amount mismatch: expected {expected_amount} tiyins, got {amount} tiyins")
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -31001,
                        "message": "Incorrect amount",
                        "data": str(expected_amount)
                    },
                    "id": params.get('id', 0)
                }

            logger.info(f"Transaction allowed for subscription ID: {account_id}, transaction_id: {transaction_id}")
            return response.CheckPerformTransaction(allow=True).as_resp()
        except Exception as e:
            logger.error(f"Unexpected error in check_perform_transaction: {str(e)} with params: {params}")
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -31000,
                    "message": "Internal server error",
                    "data": "Check server logs"
                },
                "id": params.get('id', 0)
            }

    def create_transaction(self, params):
        logger.info(f"Payme create_transaction full params: {params}")
        transaction_id = params.get('id')
        account_id = params.get('account', {}).get('id')
        amount = params.get('amount')
        time = params.get('time')

        try:
            try:
                UserSubscription.objects.get(id=int(account_id))
            except UserSubscription.DoesNotExist:
                logger.error(f"Invalid subscription ID in create_transaction: {account_id}")
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -31050,
                        "message": "Invalid subscription ID",
                        "data": "account[id]"
                    },
                    "id": params.get('id', 0)
                }

            transaction, created = PaymeTransactions.objects.update_or_create(
                transaction_id=transaction_id,
                defaults={
                    'account_id': account_id,
                    'amount': amount,
                    'state': 1,
                    'created_at': timezone.datetime.fromtimestamp(time / 1000)
                }
            )
            logger.info(f"Transaction {transaction_id} created/updated with state 1")
            return response.CreateTransaction(
                state=1,
                transaction=transaction_id,
                create_time=time
            ).as_resp()
        except Exception as e:
            logger.error(f"Error in create_transaction: {str(e)} with params: {params}")
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -31008,
                    "message": "Internal server error",
                    "data": str(e)
                },
                "id": params.get('id', 0)
            }

    def handle_successfully_payment(self, params, result, *args, **kwargs):
        logger.info(f"Payme handle_successfully_payment full params: {params}")
        try:
            transaction = PaymeTransactions.get_by_transaction_id(transaction_id=params["id"])
            account_id = transaction.account_id
            user = UserSubscription.objects.get(id=int(account_id)).user

            # Get the most recent subscription for the user (active or inactive)
            subscription = UserSubscription.objects.filter(user=user).order_by('-id').first()

            if not subscription:
                logger.error(f"No subscription found for user with account_id: {account_id}")
                return

            # Deactivate other active subscriptions for the user
            UserSubscription.objects.filter(
                user=user,
                is_active=True
            ).exclude(id=subscription.id).update(is_active=False, end_date=None)

            # Extend the existing subscription
            add_days = SUBSCRIPTION_DAYS.get(subscription.pending_extension_type or subscription.subscription_type, 30)
            if subscription.is_active and subscription.end_date:
                new_end_date = subscription.end_date + timedelta(days=add_days)
                subscription.end_date = new_end_date
                subscription.pending_extension_type = None
                subscription.save(update_fields=['end_date', 'pending_extension_type'])
                logger.info(f"✅ Extended subscription ID: {account_id}, new end_date: {new_end_date}")
            else:
                subscription.start_date = timezone.now().date()
                subscription.end_date = subscription.start_date + timedelta(days=add_days)
                subscription.is_active = True
                subscription.pending_extension_type = None
                subscription.save(update_fields=['start_date', 'end_date', 'is_active', 'pending_extension_type'])
                logger.info(f"✅ Activated subscription ID: {account_id}, is_active: {subscription.is_active}, end_date: {subscription.end_date}")

            # Update user's premium status
            subscription.user.is_premium = subscription.is_active
            subscription.user.save()
        except UserSubscription.DoesNotExist:
            logger.error(f"❌ No subscription found with ID: {account_id}")
        except Exception as e:
            logger.error(f"Error in handle_successfully_payment: {str(e)}")

    def handle_cancelled_payment(self, params, result, *args, **kwargs):
        logger.info(f"Payme handle_cancelled_payment full params: {params}")
        try:
            transaction = PaymeTransactions.get_by_transaction_id(transaction_id=params["id"])
            account_id = transaction.account_id
            subscription = UserSubscription.objects.get(id=int(account_id))
            subscription.is_active = False
            subscription.pending_extension_type = None
            subscription.save(update_fields=['is_active', 'pending_extension_type'])
            logger.info(f"✅ Cancelled payment for subscription ID: {account_id}")
        except UserSubscription.DoesNotExist:
            logger.error(f"❌ No subscription found with ID: {account_id}")
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
            f"Processing subscription for user {user.email_or_phone} with type {subscription_type}, amount {amount} so'm, expected tiyins: {amount * 100}")

        # Get the most recent subscription for the user (active or inactive)
        subscription = UserSubscription.objects.filter(user=user).order_by('-id').first()

        if not subscription:
            # Create a new subscription only if no records exist
            subscription = UserSubscription.objects.create(
                user=user,
                subscription_type=subscription_type,
                amount_in_soum=amount,
                is_active=False,
                start_date=timezone.now().date(),
                end_date=None,
                pending_extension_type=subscription_type
            )
            logger.info(f"Created new subscription ID: {subscription.id} for user {user.email_or_phone}, amount_in_soum: {amount}")
        else:
            # Reuse existing subscription and update it
            logger.info(
                f"Found subscription ID: {subscription.id} for user {user.email_or_phone}, is_active: {subscription.is_active}, current amount_in_soum: {subscription.amount_in_soum}")
            subscription.amount_in_soum = amount
            subscription.pending_extension_type = subscription_type
            subscription.save(update_fields=['amount_in_soum', 'pending_extension_type'])
            logger.info(f"Updated subscription ID: {subscription.id}, new amount_in_soum: {amount}")

        if payment_method == "payme":
            existing_transactions = PaymeTransactions.objects.filter(account__id=subscription.id)
            for transaction in existing_transactions:
                logger.info(
                    f"Existing transaction: ID {transaction.transaction_id}, State {transaction.state}, Account ID: {transaction.account_id}")

            user_program_id = str(subscription.id)
            logger.info(f"Using account ID for Payme: {user_program_id}")

            payme_url = generate_payme_docs_style_url(
                subscription_type=subscription_type,
                user_program_id=user_program_id
            )
            logger.info(f"Payme redirect URL generated: {payme_url}")
            return Response({"redirect_url": payme_url})

        elif payment_method == "click":
            return_url = "https://owntrainer.uz/payment-success"
            amount_in_tiyins = amount  # Ensure conversion to tiyins for Click
            pay_url = PyClick.generate_url(
                order_id=str(subscription.id),
                amount=str(amount_in_tiyins),
                return_url=return_url
            )
            logger.info(f"Click redirect URL: {pay_url}, Request data: {request.data}, amount in tiyins: {amount_in_tiyins}")
            return Response({"redirect_url": pay_url})

        return Response({"error": "Unhandled payment method"}, status=500)
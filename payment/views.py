from payme.types import response
from payme.views import PaymeWebHookAPIView
from payme.models import PaymeTransactions
from users_app.models import UserProgram, UserSubscription
from django.utils import timezone
from datetime import timedelta




from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from click_app.views import SUBSCRIPTION_COSTS  # import from click.views
from click_app.views import PyClick  # Click payment generator
from django.conf import settings


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

    from payme.types import response

    def check_perform_transaction(self, params):
        try:
            user_program = self.fetch_account(params)
            amount = int(params.get('amount'))
            expected_amount = user_program.amount

            # If amount is wrong, return code -31001 with "data":"amount"
            if amount != expected_amount:
                return response.CheckPerformTransaction(
                    allow=False,
                    reason=-31001,  # <-- important!
                    message="Неверная сумма",
                    data="amount"
                ).as_resp()

            # Otherwise, transaction is allowed
            return response.CheckPerformTransaction(allow=True).as_resp()

        except UserProgram.DoesNotExist:
            # If user program is invalid, return a relevant code (e.g. -31050)
            return response.CheckPerformTransaction(
                allow=False,
                reason=-31050,
                message="Invalid user program ID",
                data="account[id]"
            ).as_resp()

        except Exception as e:
            # For other errors, you can return a generic -31008 or any relevant code
            return response.CheckPerformTransaction(
                allow=False,
                reason=-31008,
                message=str(e)
            ).as_resp()

    def handle_successfully_payment(self, params, result, *args, **kwargs):
        transaction = PaymeTransactions.get_by_transaction_id(transaction_id=params["id"])
        user_program_id = transaction.account.id
        try:
            user_program = UserProgram.objects.get(id=user_program_id)
            user = user_program.user
            sub_type = user_program.subscription_type
            add_days = SUBSCRIPTION_DAYS.get(sub_type, 30)
            today = timezone.now().date()

            # Ensure the program's goal matches the user's goal
            if user_program.program and user_program.program.program_goal != user.goal:
                raise ValueError("Program goal does not match user goal")

            # Ensure subscription is active
            user_subscription, created = UserSubscription.objects.get_or_create(
                user=user, is_active=True, defaults={"subscription_type": sub_type}
            )
            user_subscription.extend_subscription(add_days)

            # Create sessions after payment using the new unified logic.
            self.create_sessions_for_user(user, user_program.program)

            # Mark the user program as paid
            user_program.is_paid = True
            user_program.save()
        except UserProgram.DoesNotExist:
            print(f"❌ No order found with ID: {user_program_id}")
        except ValueError as e:
            print(f"❌ Error: {str(e)}")

    def handle_cancelled_payment(self, params, result, *args, **kwargs):
        """
        Handles canceled payments by ensuring the subscription remains unaffected.
        """
        transaction = PaymeTransactions.get_by_transaction_id(transaction_id=params["id"])
        user_program_id = transaction.account.id
        try:
            user_program = UserProgram.objects.get(id=user_program_id)
            user_program.is_paid = False
            user_program.save()
        except UserProgram.DoesNotExist:
            print(f"❌ No order found with ID: {user_program_id}")


from .utils import generate_payme_docs_style_url


class UnifiedPaymentInitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_method = request.data.get("payment_method")
        subscription_type = request.data.get("subscription_type")
        program_id = request.data.get("program_id")  # Require program_id in the request

        if subscription_type not in SUBSCRIPTION_COSTS:
            return Response({"error": "Invalid subscription_type"}, status=400)

        if payment_method not in ["click", "payme"]:
            return Response({"error": "Invalid payment_method"}, status=400)

        if not program_id:
            return Response({"error": "program_id is required"}, status=400)

        user = request.user
        amount = SUBSCRIPTION_COSTS[subscription_type]

        # Validate the program
        try:
            program = Program.objects.get(id=program_id, is_active=True)
        except Program.DoesNotExist:
            return Response({"error": "Invalid or inactive program_id"}, status=400)

        # Ensure the program matches the user's goal
        if program.program_goal != user.goal:
            return Response({"error": "Selected program does not match your goal"}, status=400)

        # Update or create subscription object
        subscription, _ = UserSubscription.objects.get_or_create(user=user, is_active=True)
        subscription.subscription_type = subscription_type
        subscription.is_active = False  # Set to True only after successful payment
        subscription.save()

        # Update or create a UserProgram
        user_program, created = UserProgram.objects.get_or_create(
            user=user,
            is_active=True,
            defaults={"program": program, "amount": amount, "subscription_type": subscription_type}
        )
        if not created:
            user_program.program = program
            user_program.amount = amount
            user_program.subscription_type = subscription_type
            user_program.save()

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
                user_program_id=user_program.id
            )
            return Response({"redirect_url": payme_url})

        return Response({"error": "Unhandled payment method"}, status=500)
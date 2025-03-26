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

    def check_perform_transaction(self, params):
        """
        Validates whether a transaction can be performed.
        Payme calls this method to check if the transaction is possible
        (e.g., if the account exists, and amounts match).
        """

        try:
            # 'fetch_account(params)' returns a 'UserProgram' instance
            user_program = self.fetch_account(params)  # It's already a UserProgram model object

            amount = int(params.get('amount'))
            expected_amount = user_program.amount

            if amount != expected_amount:
                return response.CheckPerformTransaction(allow=False, message="Invalid payment amount").as_resp()

            return response.CheckPerformTransaction(allow=True).as_resp()

        except UserProgram.DoesNotExist:
            # If 'fetch_account()' or subsequent logic fails to find a valid UserProgram
            return response.CheckPerformTransaction(
                allow=False,
                message="Invalid user program ID"
            ).as_resp()

        except Exception as e:
            # Any other unexpected error
            return response.CheckPerformTransaction(
                allow=False,
                message=f"Error: {str(e)}"
            ).as_resp()

    def handle_successfully_payment(self, params, result, *args, **kwargs):
        """
        Handles successful payments and extends the user's subscription.
        """
        transaction = PaymeTransactions.get_by_transaction_id(transaction_id=params["id"])
        user_program_id = transaction.account.id
        try:
            user_program = UserProgram.objects.get(id=user_program_id)
            user = user_program.user
            sub_type = user_program.subscription_type
            add_days = SUBSCRIPTION_DAYS.get(sub_type, 30)
            today = timezone.now().date()

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

    def create_sessions_for_user(self, user, program):
        """
        Generates session records **only after payment is successful** using the new unified flow.
        Creates SessionCompletion, MealCompletion, and ExerciseBlockCompletion records.
        """
        from users_app.models import SessionCompletion, MealCompletion, ExerciseBlockCompletion
        sessions = program.sessions.order_by("session_number")
        start_date = timezone.now().date()

        for index, session in enumerate(sessions, start=1):
            session_date = start_date + timedelta(days=index - 1)
            SessionCompletion.objects.create(
                user=user,
                session=session,
                is_completed=False,
                session_number_private=session.session_number,
                session_date=session_date,
            )
            for meal in session.meals.all():
                MealCompletion.objects.create(
                    user=user,
                    meal=meal,
                    session=session,
                    is_completed=False,
                    meal_date=session_date,
                )
            if hasattr(session, 'block'):
                ExerciseBlockCompletion.objects.create(
                    user=user,
                    block=session.block,
                    is_completed=False
                )
    # End of PaymeCallBackAPIView








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
        subscription, _ = UserSubscription.objects.get_or_create(user=user, is_active=True)
        subscription.subscription_type = subscription_type
        subscription.is_active = False  # Set to True only after successful payment
        subscription.save()

        # Create a UserProgram (for Payme callbacks)
        user_program = UserProgram.objects.create(user=user, program=None, amount=amount)

        if payment_method == "click":
            return_url = "https://owntrainer.uz/payment/success"
            pay_url = PyClick.generate_url(order_id=subscription.id, amount=str(amount), return_url=return_url)
            return Response({"redirect_url": pay_url})

        elif payment_method == "payme":
            payme_url = (
                f"https://checkout.paycom.uz/{settings.PAYME_ID}"
                f"?account[id]={user_program.id}&amount={amount * 100}"
            )
            return Response({"redirect_url": payme_url})

        return Response({"error": "Unhandled payment method"}, status=500)

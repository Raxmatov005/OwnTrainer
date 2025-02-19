# payme/views.py

from payme.types import response
from payme.views import PaymeWebHookAPIView
from payme.models import PaymeTransactions
from users_app.models import UserProgram, UserSubscription
from django.utils import timezone
from datetime import timedelta

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
        """
        account = self.fetch_account(params)
        user_program_id = account.get('id')

        try:
            user_program = UserProgram.objects.get(id=user_program_id)
            amount = int(params.get('amount'))

            # Ensure the amount matches the expected subscription cost
            expected_amount = user_program.amount
            if amount != expected_amount:
                return response.CheckPerformTransaction(allow=False, message="Invalid payment amount").as_resp()

            return response.CheckPerformTransaction(allow=True).as_resp()
        except UserProgram.DoesNotExist:
            return response.CheckPerformTransaction(allow=False, message="Invalid user program ID").as_resp()

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

            # ✅ Use `UserSubscription` to track active subscription
            user_subscription, created = UserSubscription.objects.get_or_create(
                user=user, is_active=True, defaults={"subscription_type": sub_type}
            )

            user_subscription.extend_subscription(add_days)

            # ✅ Create sessions after payment
            self.create_sessions_for_user(user, user_program.program)

            # ✅ Mark as paid
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
        Generates session records **only after payment is successful**.
        """
        from users_app.models import SessionCompletion, MealCompletion, ExerciseCompletion

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

            for exercise in session.exercises.all():
                ExerciseCompletion.objects.create(
                    user=user,
                    exercise=exercise,
                    session=session,
                    is_completed=False,
                    exercise_date=session_date,
                )

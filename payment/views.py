# payme/views.py

from payme.types import response
from payme.views import PaymeWebHookAPIView
from payme.models import PaymeTransactions
from users_app.models import UserProgram
from django.utils import timezone
from datetime import timedelta

# Reuse the same dict from above if you like:
SUBSCRIPTION_DAYS = {
    'month': 30,
    'quarter': 90,
    'year': 365
}

class PaymeCallBackAPIView(PaymeWebHookAPIView):
    """
    A view to handle Payme Webhook API calls for subscription.
    """

    def check_perform_transaction(self, params):
        account = self.fetch_account(params)
        self.validate_amount(account, params.get('amount'))
        result = response.CheckPerformTransaction(allow=True)
        return result.as_resp()

    def handle_successfully_payment(self, params, result, *args, **kwargs):
        transaction = PaymeTransactions.get_by_transaction_id(
            transaction_id=params["id"]
        )
        # The 'id' in your 'account' might be user_program id:
        user_program_id = transaction.account.id  
        user_program = UserProgram.objects.get(id=user_program_id)

        user_program.is_paid = True

        # Extend subscription
        sub_type = user_program.subscription_type
        add_days = SUBSCRIPTION_DAYS.get(sub_type, 30)

        today = timezone.now().date()
        old_end = user_program.end_date if user_program.end_date else today
        base_date = old_end if old_end >= today else today
        new_end = base_date + timedelta(days=add_days)

        user_program.start_date = today
        user_program.end_date = new_end
        user_program.save()

    def handle_cancelled_payment(self, params, result, *args, **kwargs):
        transaction = PaymeTransactions.get_by_transaction_id(
            transaction_id=params["id"]
        )
        # In case of cancellation, mark is_paid=False or do nothing:
        user_program_id = transaction.account.id
        user_program = UserProgram.objects.get(id=user_program_id)
        user_program.is_paid = False
        user_program.save()

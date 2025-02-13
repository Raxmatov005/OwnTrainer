# click/views.py

from django.utils import timezone
from django.shortcuts import redirect
from rest_framework.generics import CreateAPIView
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from pyclick import PyClick
from pyclick.views import PyClickMerchantAPIView

from . import serializers
from users_app.models import UserProgram
from datetime import timedelta

# Example price / duration settings:
SUBSCRIPTION_COSTS = {
    'month': 10000,       # e.g. 10,000
    'quarter': 25000,     # e.g. 25,000
    'year': 90000         # e.g. 90,000
}
SUBSCRIPTION_DAYS = {
    'month': 30,
    'quarter': 90,
    'year': 365
}

class CreateClickOrderView(CreateAPIView):
    """
    This view accepts a subscription_type from the request,
    creates or updates the user's subscription (UserProgram),
    and returns the Click payment URL for them to pay.
    """
    serializer_class = serializers.ClickOrderSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # 1. Validate input: subscription_type must be in {'month','quarter','year'}
        subscription_type = request.data.get('subscription_type')
        if subscription_type not in SUBSCRIPTION_COSTS:
            return Response({"error": "Invalid subscription_type. Must be month, quarter, or year."}, status=400)

        # 2. Get the cost & days
        amount = SUBSCRIPTION_COSTS[subscription_type]
        add_days = SUBSCRIPTION_DAYS[subscription_type]

        # You might need an authenticated user. If you're letting
        # an unauthenticated user do this, adapt accordingly.
        # For example, if your authentication is different, fix as needed.
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "User must be logged in."}, status=401)

        # 3. Check if user has an existing subscription row in UserProgram
        #    (You can either create a new row each time or reuse the same row)
        user_program = UserProgram.objects.filter(user=user).first()
        if not user_program:
            # create a new one
            user_program = UserProgram.objects.create(
                user=user,
                subscription_type=subscription_type,
                payment_method='click',
                is_paid=False
            )
        else:
            # update subscription_type
            user_program.subscription_type = subscription_type
            user_program.payment_method = 'click'
            user_program.is_paid = False
            user_program.save()

        # 4. We store the cost in `amount`. We'll finalize the end_date on success,
        #    or we can pre-set an expected end_date if we like. For now, let's do it on success.
        user_program.amount = amount
        user_program.save()

        # 5. Generate the payment URL using PyClick
        #    (We assume the 'id' param is our user_program.id, and 'amount' is the sum.)
        #    If your click config demands different param names, adjust accordingly.
        return_url = 'https://owntrainer.uz/'  # or your actual return page
        pay_url = PyClick.generate_url(
            order_id=user_program.id,
            amount=str(amount),
            return_url=return_url
        )

        return redirect(pay_url)


class OrderCheckAndPayment(PyClick):
    """
    This is the logic that Click uses to check orders and finalize payment.
    On success, we set user_program.is_paid = True and adjust end_date.
    """

    def check_order(self, order_id: str, amount: str):
        if order_id:
            try:
                order = UserProgram.objects.get(id=order_id)
                # Confirm the amounts match
                if int(amount) == order.amount:
                    return self.ORDER_FOUND
                else:
                    return self.INVALID_AMOUNT
            except UserProgram.DoesNotExist:
                return self.ORDER_NOT_FOUND


    def successfully_payment(self, order_id: str, transaction: object):
        """
        Called when Click notifies us that payment is successful.
        We'll mark the subscription as paid and adjust the end_date.
        """
        try:
            user_program = UserProgram.objects.get(id=order_id)
            user_program.is_paid = True

            # Figure out how many days to add based on subscription_type
            sub_type = user_program.subscription_type
            add_days = SUBSCRIPTION_DAYS.get(sub_type, 30)

            # If the user already had some leftover time, extend from old end_date
            today = timezone.now().date()
            old_end = user_program.end_date if user_program.end_date else today

            # If subscription is still valid, we extend from that date,
            # else we start from today
            base_date = old_end if old_end >= today else today
            new_end = base_date + timedelta(days=add_days)

            user_program.start_date = today
            user_program.end_date = new_end
            user_program.save()

        except UserProgram.DoesNotExist:
            print(f"No order found with ID: {order_id}")


class OrderTestView(PyClickMerchantAPIView):
    """
    This is the endpoint that Click calls for check/complete.
    We link it to the above OrderCheckAndPayment class logic.
    """
    VALIDATE_CLASS = OrderCheckAndPayment

from django.http import JsonResponse
from django.shortcuts import redirect
from rest_framework.generics import CreateAPIView
from rest_framework.views import APIView
from . import serializers
from users_app.models import UserProgram
from rest_framework.permissions import AllowAny


# Correct imports for your Click integration classes:
from pyclick import PyClick
from pyclick.views import PyClickMerchantAPIView  # or from pyclick.views import PyClickMerchantAPIView

class CreateClickOrderView(CreateAPIView):
    serializer_class = serializers.ClickOrderSerializer
    permission_classes = [AllowAny]


    def post(self, request, *args, **kwargs):
        amount = request.POST.get('amount')
        order = UserProgram.objects.create(amount=amount)
        return_url = 'https://owntrainer.uz/'
        url = PyClick.generate_url(order_id=order.id, amount=str(amount), return_url=return_url)
        return redirect(url)

class OrderCheckAndPayment(PyClick):
    def check_order(self, order_id: str, amount: str):
        if order_id:
            try:
                order = UserProgram.objects.get(id=order_id)
                if int(amount) == order.amount:
                    return self.ORDER_FOUND
                else:
                    return self.INVALID_AMOUNT
            except UserProgram.DoesNotExist:
                return self.ORDER_NOT_FOUND

    def successfully_payment(self, order_id: str, transaction: object):
        try:
            order = UserProgram.objects.get(id=order_id)
            order.is_paid = True
            order.save()
        except UserProgram.DoesNotExist:
            print(f"No order found with ID: {order_id}")

class OrderTestView(PyClickMerchantAPIView):
    VALIDATE_CLASS = OrderCheckAndPayment

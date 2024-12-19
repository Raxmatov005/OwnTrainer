

from rest_framework import serializers
from users_app.models import UserProgram

class ClickOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProgram
        fields = ["amount", "is_paid"]
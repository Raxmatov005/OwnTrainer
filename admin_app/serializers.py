from rest_framework import serializers

class AdminLoginSerializer(serializers.Serializer):
    email_or_phone = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

from rest_framework import serializers
from .models import Payment

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Payment
        fields = ['id', 'transaction_id', 'order_id', 'amount', 'method', 'status', 'gateway_response', 'timestamp']
        read_only_fields = ['id', 'transaction_id', 'timestamp', 'gateway_response']

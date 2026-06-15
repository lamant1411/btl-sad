from rest_framework import serializers
from .models import Shipment, ShipmentHistory

class ShipmentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = ShipmentHistory
        fields = ['status', 'location', 'note', 'timestamp']

class ShipmentSerializer(serializers.ModelSerializer):
    history = ShipmentHistorySerializer(many=True, read_only=True)
    class Meta:
        model  = Shipment
        fields = ['id', 'order_id', 'carrier', 'tracking_code', 'status',
                  'recipient_name', 'recipient_address', 'estimated_delivery',
                  'actual_delivery', 'history', 'created_at', 'updated_at']

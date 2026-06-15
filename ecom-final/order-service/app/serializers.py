from rest_framework import serializers
from .models import Order, OrderItem

class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.ReadOnlyField()
    class Meta:
        model  = OrderItem
        fields = ['id', 'product_id', 'quantity', 'unit_price', 'subtotal']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    class Meta:
        model  = Order
        fields = ['id', 'customer_id', 'total_price', 'status', 'note', 'items', 'created_at', 'updated_at']

class OrderItemCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity   = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)

class OrderCreateSerializer(serializers.Serializer):
    customer_id     = serializers.IntegerField()
    items           = OrderItemCreateSerializer(many=True)
    note            = serializers.CharField(required=False, allow_blank=True, default='')
    payment_method  = serializers.CharField(required=False, default='COD')

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Đơn hàng phải có ít nhất 1 sản phẩm.")
        return value

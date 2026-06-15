from rest_framework import serializers
from .models import Cart, CartItem

class CartItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CartItem
        fields = ['id', 'product_id', 'quantity', 'unit_price', 'added_at']

class CartSerializer(serializers.ModelSerializer):
    items       = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    def get_total_price(self, obj):
        return sum(i.quantity * i.unit_price for i in obj.items.all())

    class Meta:
        model  = Cart
        fields = ['id', 'customer_id', 'items', 'total_price', 'created_at', 'updated_at']

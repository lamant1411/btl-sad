from rest_framework import serializers
from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Category
        fields = ['slug', 'name', 'description', 'icon']


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_slug = serializers.CharField(write_only=True, source='category_id')

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'description', 'price', 'stock',
            'category', 'category_slug', 'attributes',
            'image_url', 'is_active', 'created_at', 'version'
        ]
        read_only_fields = ['id', 'created_at', 'version']


class ProductListSerializer(serializers.ModelSerializer):
    """Phiên bản nhẹ hơn cho danh sách — không trả về attributes đầy đủ."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)

    class Meta:
        model  = Product
        fields = ['id', 'name', 'price', 'stock', 'category_name',
                  'category_slug', 'image_url', 'is_active']


class StockUpdateSerializer(serializers.Serializer):
    """Payload cho API cập nhật tồn kho (Optimistic Locking)."""
    delta           = serializers.IntegerField(help_text="Số lượng thay đổi (+/-)")
    expected_version = serializers.IntegerField(help_text="Version hiện tại để tránh conflict")

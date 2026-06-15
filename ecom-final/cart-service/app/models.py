"""Cart Service — Models"""
from django.db import models


class Cart(models.Model):
    """
    Giỏ hàng của khách hàng.
    customer_id là soft reference sang User Service — không có FK.
    """
    customer_id = models.IntegerField(unique=True, db_index=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart#{self.id} (customer={self.customer_id})"

    class Meta:
        db_table = 'carts'


class CartItem(models.Model):
    """
    Sản phẩm trong giỏ hàng.
    product_id là soft reference sang Product Service — không có FK.
    """
    cart       = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product_id = models.IntegerField(db_index=True)
    quantity   = models.PositiveIntegerField(default=1)
    # Cache giá tại thời điểm thêm vào giỏ (Eventual Consistency)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    added_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'cart_items'
        unique_together = [('cart', 'product_id')]

    def __str__(self):
        return f"CartItem(product={self.product_id}, qty={self.quantity})"

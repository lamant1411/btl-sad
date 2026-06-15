"""Order Service — Models"""
from django.db import models


class Order(models.Model):
    """
    Đơn hàng — Aggregate Root của Saga Pattern.
    Không FK xuyên service, dùng soft reference.
    """
    STATUS_PENDING   = 'PENDING'
    STATUS_PAID      = 'PAID'
    STATUS_SHIPPED   = 'SHIPPED'
    STATUS_DELIVERED = 'DELIVERED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (STATUS_PENDING,   'Chờ xử lý'),
        (STATUS_PAID,      'Đã thanh toán'),
        (STATUS_SHIPPED,   'Đang giao'),
        (STATUS_DELIVERED, 'Đã giao'),
        (STATUS_CANCELLED, 'Đã hủy'),
    ]

    customer_id = models.IntegerField(db_index=True)      # Soft ref → User Service
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    note        = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order#{self.id} [{self.status}] customer={self.customer_id}"

    class Meta:
        db_table = 'orders'
        indexes  = [models.Index(fields=['customer_id', 'status'])]


class OrderItem(models.Model):
    """Dòng sản phẩm trong đơn hàng."""
    order      = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product_id = models.IntegerField()         # Soft ref → Product Service
    quantity   = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    class Meta:
        db_table = 'order_items'

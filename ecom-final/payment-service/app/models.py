"""Payment Service — Models"""
from django.db import models
import uuid


class Payment(models.Model):
    """
    Giao dịch thanh toán với Idempotency Key (transaction_id UUID).
    order_id là soft reference sang Order Service.
    """
    STATUS_PROCESSING = 'PROCESSING'
    STATUS_SUCCESS    = 'SUCCESS'
    STATUS_FAILED     = 'FAILED'
    STATUS_REFUNDED   = 'REFUNDED'

    STATUS_CHOICES = [
        (STATUS_PROCESSING, 'Đang xử lý'),
        (STATUS_SUCCESS,    'Thành công'),
        (STATUS_FAILED,     'Thất bại'),
        (STATUS_REFUNDED,   'Đã hoàn tiền'),
    ]

    METHOD_COD    = 'COD'
    METHOD_VNPAY  = 'VNPAY'
    METHOD_MOMO   = 'MOMO'
    METHOD_STRIPE = 'STRIPE'

    METHOD_CHOICES = [
        (METHOD_COD,    'Thanh toán khi nhận hàng'),
        (METHOD_VNPAY,  'VNPay'),
        (METHOD_MOMO,   'MoMo'),
        (METHOD_STRIPE, 'Stripe'),
    ]

    # Idempotency key — đảm bảo không xử lý trùng giao dịch
    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    order_id       = models.IntegerField(db_index=True)   # Soft ref → Order Service
    amount         = models.DecimalField(max_digits=12, decimal_places=2)
    method         = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_COD)
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PROCESSING)
    # Lưu response từ payment gateway (webhook payload)
    gateway_response = models.JSONField(default=dict, blank=True)
    timestamp      = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.transaction_id} | Order#{self.order_id} | {self.status}"

    class Meta:
        db_table = 'payments'
        indexes  = [models.Index(fields=['order_id'])]

"""Shipping Service — Models"""
from django.db import models


class Shipment(models.Model):
    """
    Thông tin vận chuyển cho đơn hàng.
    order_id là soft reference sang Order Service.
    """
    STATUS_PENDING   = 'PENDING'
    STATUS_PICKED_UP = 'PICKED_UP'
    STATUS_IN_TRANSIT = 'IN_TRANSIT'
    STATUS_OUT_FOR_DELIVERY = 'OUT_FOR_DELIVERY'
    STATUS_DELIVERED = 'DELIVERED'
    STATUS_FAILED    = 'FAILED'

    STATUS_CHOICES = [
        (STATUS_PENDING,            'Chờ lấy hàng'),
        (STATUS_PICKED_UP,          'Đã lấy hàng'),
        (STATUS_IN_TRANSIT,         'Đang vận chuyển'),
        (STATUS_OUT_FOR_DELIVERY,   'Đang giao'),
        (STATUS_DELIVERED,          'Đã giao'),
        (STATUS_FAILED,             'Giao thất bại'),
    ]

    CARRIER_GHTK   = 'GHTK'
    CARRIER_GHN    = 'GHN'
    CARRIER_VNPOST = 'VNPOST'
    CARRIER_VIETTEL = 'VIETTEL'

    CARRIER_CHOICES = [
        (CARRIER_GHTK,    'Giao Hàng Tiết Kiệm'),
        (CARRIER_GHN,     'Giao Hàng Nhanh'),
        (CARRIER_VNPOST,  'VNPost'),
        (CARRIER_VIETTEL, 'Viettel Post'),
    ]

    order_id         = models.IntegerField(unique=True, db_index=True)  # Soft ref
    carrier          = models.CharField(max_length=20, choices=CARRIER_CHOICES, default=CARRIER_GHN)
    tracking_code    = models.CharField(max_length=100, blank=True, null=True)
    status           = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING)
    recipient_name   = models.CharField(max_length=255, blank=True)
    recipient_phone  = models.CharField(max_length=20, blank=True)
    recipient_address = models.TextField(blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)
    actual_delivery  = models.DateTimeField(null=True, blank=True)
    notes            = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Shipment#{self.id} Order#{self.order_id} [{self.status}]"

    class Meta:
        db_table = 'shipments'


class ShipmentHistory(models.Model):
    """Lịch sử tracking từng bước vận chuyển."""
    shipment  = models.ForeignKey(Shipment, related_name='history', on_delete=models.CASCADE)
    status    = models.CharField(max_length=30)
    location  = models.CharField(max_length=255, blank=True)
    note      = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table  = 'shipment_history'
        ordering  = ['-timestamp']

"""Order Service — Views (Saga Orchestrator)"""
import json
import logging
import requests
import redis as redis_client
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Order, OrderItem
from .serializers import OrderSerializer, OrderCreateSerializer

logger = logging.getLogger(__name__)


def _get_redis():
    return redis_client.from_url(
        getattr(settings, 'REDIS_URL', 'redis://redis:6379/0'),
        decode_responses=True
    )


def _call_service(method: str, url: str, **kwargs) -> requests.Response | None:
    """Helper với timeout + try-except cho mọi inter-service call."""
    kwargs.setdefault('timeout', 3.0)
    try:
        return getattr(requests, method)(url, **kwargs)
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout khi gọi {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed {url}: {e}")
        return None


class OrderListView(APIView):
    """GET /api/orders/?customer_id=<id> — Lịch sử đơn hàng."""

    def get(self, request):
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return Response({"error": "customer_id là bắt buộc."}, status=status.HTTP_400_BAD_REQUEST)
        orders = Order.objects.filter(customer_id=customer_id).prefetch_related('items').order_by('-created_at')
        return Response(OrderSerializer(orders, many=True).data)


class OrderCreateView(APIView):
    """
    POST /api/orders/
    Saga Orchestrator:
      1. Tạo Order (PENDING)
      2. Xóa Cart
      3. Gọi Payment Service
      4. Publish ORDER_CREATED event vào Redis PubSub
    """

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data        = serializer.validated_data
        customer_id = data['customer_id']
        items_data  = data['items']

        # ── Step 1: Tạo Order trong DB cục bộ ──────────────────
        total_price = sum(
            item['unit_price'] * item['quantity'] for item in items_data
        )
        order = Order.objects.create(
            customer_id=customer_id,
            total_price=total_price,
            status=Order.STATUS_PENDING,
            note=data.get('note', '')
        )
        for item in items_data:
            OrderItem.objects.create(
                order=order,
                product_id=item['product_id'],
                quantity=item['quantity'],
                unit_price=item['unit_price']
            )
        logger.info(f"Order#{order.id} created (PENDING) for customer={customer_id}")

        # ── Step 2: Xóa Cart (Saga Step) ───────────────────────
        cart_url = getattr(settings, 'CART_SERVICE_URL', 'http://cart-service:8002')
        _call_service('delete', f"{cart_url}/api/carts/{customer_id}/")

        # ── Step 3: Gọi Payment Service (Saga Step) ─────────────
        pay_url = getattr(settings, 'PAYMENT_SERVICE_URL', 'http://payment-service:8004')
        pay_resp = _call_service('post', f"{pay_url}/api/payments/", json={
            'order_id': order.id,
            'amount':   str(total_price),
            'method':   data.get('payment_method', 'COD')
        })

        if pay_resp and pay_resp.status_code == 201:
            logger.info(f"Order#{order.id} — Payment initiated successfully.")
        else:
            logger.warning(f"Order#{order.id} — Payment Service unavailable, order stays PENDING.")

        # ── Step 4: Publish Event vào Redis PubSub ──────────────
        event_channel = getattr(settings, 'ORDER_EVENTS_CHANNEL', 'order.events')
        event_payload = json.dumps({
            'event':       'ORDER_CREATED',
            'order_id':    order.id,
            'customer_id': customer_id,
            'total_price': str(total_price),
            'items': [
                {'product_id': i['product_id'], 'quantity': i['quantity']}
                for i in items_data
            ]
        })
        try:
            r = _get_redis()
            r.publish(event_channel, event_payload)
            logger.info(f"Order#{order.id} — EVENT ORDER_CREATED published to '{event_channel}'")
        except Exception as e:
            logger.warning(f"Redis publish failed: {e}")

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetailView(APIView):
    """
    GET   /api/orders/<pk>/ — Chi tiết đơn hàng.
    PATCH /api/orders/<pk>/ — Cập nhật status (webhook từ Payment/Shipping).
    """

    def get(self, request, pk):
        try:
            order = Order.objects.prefetch_related('items').get(pk=pk)
            return Response(OrderSerializer(order).data)
        except Order.DoesNotExist:
            return Response({"error": "Đơn hàng không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({"error": "Đơn hàng không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        if new_status not in [s[0] for s in Order.STATUS_CHOICES]:
            return Response({"error": f"Status không hợp lệ: {new_status}"}, status=status.HTTP_400_BAD_REQUEST)

        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])
        logger.info(f"Order#{pk} status updated to {new_status}")

        # Publish event nếu chuyển sang PAID
        if new_status == Order.STATUS_PAID:
            event_channel = getattr(settings, 'ORDER_EVENTS_CHANNEL', 'order.events')
            try:
                r = _get_redis()
                r.publish(event_channel, json.dumps({
                    'event':    'ORDER_PAID',
                    'order_id': pk,
                }))
            except Exception as e:
                logger.warning(f"Redis publish ORDER_PAID failed: {e}")

        return Response(OrderSerializer(order).data)

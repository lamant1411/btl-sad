"""Payment Service — Views + PubSub Listener"""
import json
import logging
import threading
import requests
import redis as redis_client
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Payment
from .serializers import PaymentSerializer

logger = logging.getLogger(__name__)


def _notify_order_paid(order_id: int):
    """Webhook ngược lại Order Service để cập nhật status = PAID."""
    order_url = getattr(settings, 'ORDER_SERVICE_URL', 'http://order-service:8003')
    try:
        requests.patch(
            f"{order_url}/api/orders/{order_id}/",
            json={"status": "PAID"},
            timeout=3.0
        )
        logger.info(f"Order#{order_id} notified as PAID.")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to notify Order Service for order#{order_id}: {e}")


class PaymentProcessView(APIView):
    """
    POST /api/payments/
    Tạo giao dịch với Idempotency: kiểm tra order_id chưa được thanh toán thành công.
    """

    def post(self, request):
        order_id = request.data.get('order_id')

        # Idempotency check: mỗi order chỉ được SUCCESS một lần
        existing = Payment.objects.filter(
            order_id=order_id,
            status=Payment.STATUS_SUCCESS
        ).first()
        if existing:
            return Response(
                {"error": "Order này đã được thanh toán.", "transaction_id": str(existing.transaction_id)},
                status=status.HTTP_409_CONFLICT
            )

        serializer = PaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Giả lập gọi Payment Gateway (VNPay, MoMo...)
        # Trong thực tế: gọi API bên thứ 3 và xử lý webhook IPN
        payment = serializer.save(
            status=Payment.STATUS_SUCCESS,
            gateway_response={"simulated": True, "code": "00", "message": "Giao dịch thành công"}
        )

        logger.info(f"Payment {payment.transaction_id} SUCCESS for Order#{order_id}")

        # Callback webhook sang Order Service (bất đồng bộ)
        thread = threading.Thread(target=_notify_order_paid, args=(order_id,), daemon=True)
        thread.start()

        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class PaymentDetailView(APIView):
    """GET /api/payments/<order_id>/ — Tra cứu thanh toán theo order_id."""

    def get(self, request, order_id):
        try:
            payment = Payment.objects.get(order_id=order_id)
            return Response(PaymentSerializer(payment).data)
        except Payment.DoesNotExist:
            return Response({"error": "Không tìm thấy giao dịch."}, status=status.HTTP_404_NOT_FOUND)


# ── Redis PubSub Listener (chạy trong background thread) ──────────────────────
def start_pubsub_listener():
    """
    Lắng nghe kênh order.events từ Redis PubSub.
    Chạy trong daemon thread — không block gunicorn workers.
    """
    redis_url     = getattr(settings, 'REDIS_URL', 'redis://redis:6379/0')
    event_channel = getattr(settings, 'ORDER_EVENTS_CHANNEL', 'order.events')

    def _listen():
        while True:
            try:
                r      = redis_client.from_url(redis_url, decode_responses=True)
                pubsub = r.pubsub()
                pubsub.subscribe(event_channel)
                logger.info(f"[Payment PubSub] Listening on channel '{event_channel}'")

                for message in pubsub.listen():
                    if message['type'] != 'message':
                        continue
                    try:
                        event = json.loads(message['data'])
                        logger.info(f"[Payment PubSub] Received: {event.get('event')}")
                        # Có thể xử lý ORDER_CANCELLED để refund ở đây
                    except json.JSONDecodeError:
                        logger.warning(f"[Payment PubSub] Invalid JSON: {message['data']}")

            except Exception as e:
                import time
                logger.error(f"[Payment PubSub] Error: {e}. Reconnecting in 5s...")
                time.sleep(5)

    thread = threading.Thread(target=_listen, name='payment-pubsub', daemon=True)
    thread.start()
    logger.info("[Payment PubSub] Background listener thread started.")

"""Shipping Service — Views + PubSub Listener"""
import json, logging, threading, time
import requests, redis as redis_client
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Shipment, ShipmentHistory
from .serializers import ShipmentSerializer

logger = logging.getLogger(__name__)


class ShipmentDetailView(APIView):
    """GET /api/shipping/<order_id>/ — Tracking vận chuyển theo order."""

    def get(self, request, order_id):
        try:
            shipment = Shipment.objects.prefetch_related('history').get(order_id=order_id)
            return Response(ShipmentSerializer(shipment).data)
        except Shipment.DoesNotExist:
            return Response({"error": "Không tìm thấy thông tin vận chuyển."}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, order_id):
        """Cập nhật trạng thái vận chuyển."""
        try:
            shipment = Shipment.objects.get(order_id=order_id)
        except Shipment.DoesNotExist:
            return Response({"error": "Không tìm thấy."}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        location   = request.data.get('location', '')
        note       = request.data.get('note', '')

        if new_status:
            shipment.status = new_status
            shipment.save(update_fields=['status', 'updated_at'])
            ShipmentHistory.objects.create(shipment=shipment, status=new_status, location=location, note=note)

            # Cập nhật Order Service khi DELIVERED
            if new_status == Shipment.STATUS_DELIVERED:
                order_url = getattr(settings, 'ORDER_SERVICE_URL', 'http://order-service:8003')
                try:
                    requests.patch(f"{order_url}/api/orders/{order_id}/",
                                   json={"status": "DELIVERED"}, timeout=3.0)
                except requests.exceptions.RequestException:
                    pass

        return Response(ShipmentSerializer(shipment).data)


def _create_shipment_from_event(event: dict):
    """Tạo Shipment mới khi nhận ORDER_PAID event."""
    order_id = event.get('order_id')
    if not order_id:
        return
    shipment, created = Shipment.objects.get_or_create(
        order_id=order_id,
        defaults={'status': Shipment.STATUS_PENDING, 'carrier': Shipment.CARRIER_GHN}
    )
    if created:
        ShipmentHistory.objects.create(
            shipment=shipment,
            status=Shipment.STATUS_PENDING,
            note="Đơn hàng đã được xác nhận, chuẩn bị lấy hàng."
        )
        logger.info(f"Shipment created for Order#{order_id}")


def start_pubsub_listener():
    """Lắng nghe ORDER_PAID events từ Redis PubSub."""
    redis_url     = getattr(settings, 'REDIS_URL', 'redis://redis:6379/0')
    event_channel = getattr(settings, 'ORDER_EVENTS_CHANNEL', 'order.events')

    def _listen():
        while True:
            try:
                r      = redis_client.from_url(redis_url, decode_responses=True)
                pubsub = r.pubsub()
                pubsub.subscribe(event_channel)
                logger.info(f"[Shipping PubSub] Listening on '{event_channel}'")

                for message in pubsub.listen():
                    if message['type'] != 'message':
                        continue
                    try:
                        event = json.loads(message['data'])
                        event_type = event.get('event')
                        if event_type == 'ORDER_PAID':
                            _create_shipment_from_event(event)
                    except Exception as e:
                        logger.warning(f"[Shipping PubSub] Error processing event: {e}")
            except Exception as e:
                logger.error(f"[Shipping PubSub] Connection error: {e}. Retrying in 5s...")
                time.sleep(5)

    thread = threading.Thread(target=_listen, name='shipping-pubsub', daemon=True)
    thread.start()
    logger.info("[Shipping PubSub] Background listener thread started.")

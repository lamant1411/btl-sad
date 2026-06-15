"""Cart Service — Views"""
import logging
import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Cart, CartItem
from .serializers import CartSerializer, CartItemSerializer

logger = logging.getLogger(__name__)
PRODUCT_SERVICE_URL = None  # Nạp lazy từ settings


def _get_product_service_url():
    global PRODUCT_SERVICE_URL
    if PRODUCT_SERVICE_URL is None:
        PRODUCT_SERVICE_URL = getattr(settings, 'PRODUCT_SERVICE_URL', 'http://product-service:8001')
    return PRODUCT_SERVICE_URL


def _validate_product(product_id: int) -> dict | None:
    """
    Gọi Product Service để validate sản phẩm tồn tại và còn hàng.
    Resilience: timeout=3.0, trả về None nếu service down.
    """
    try:
        url  = f"{_get_product_service_url()}/api/products/{product_id}/"
        resp = requests.get(url, timeout=3.0)
        if resp.status_code == 200:
            return resp.json()
        return None
    except requests.exceptions.Timeout:
        logger.warning(f"Product Service timeout khi validate product_id={product_id}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Product Service unreachable: {e}")
        return None


class CartCreateView(APIView):
    """POST /api/carts/ — Tạo giỏ hàng rỗng (gọi bởi User Service sau register)."""

    def post(self, request):
        customer_id = request.data.get('customer_id')
        if not customer_id:
            return Response({"error": "customer_id là bắt buộc."}, status=status.HTTP_400_BAD_REQUEST)

        cart, created = Cart.objects.get_or_create(customer_id=customer_id)
        return Response(
            CartSerializer(cart).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class CartDetailView(APIView):
    """GET /api/carts/<customer_id>/ — Xem giỏ hàng."""

    def get(self, request, customer_id):
        try:
            cart = Cart.objects.prefetch_related('items').get(customer_id=customer_id)
            return Response(CartSerializer(cart).data)
        except Cart.DoesNotExist:
            return Response({"error": "Giỏ hàng không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, customer_id):
        """Xóa toàn bộ giỏ hàng sau khi checkout."""
        try:
            cart = Cart.objects.get(customer_id=customer_id)
            cart.items.all().delete()
            return Response({"message": "Đã xóa giỏ hàng."})
        except Cart.DoesNotExist:
            return Response({"error": "Giỏ hàng không tồn tại."}, status=status.HTTP_404_NOT_FOUND)


class CartItemView(APIView):
    """
    POST   /api/carts/<customer_id>/items/ — Thêm sản phẩm vào giỏ.
    PUT    /api/carts/<customer_id>/items/<product_id>/ — Cập nhật số lượng item.
    DELETE /api/carts/<customer_id>/items/<product_id>/ — Xóa item.
    """

    def post(self, request, customer_id):
        product_id = request.data.get('product_id')
        quantity   = int(request.data.get('quantity', 1))

        if not product_id:
            return Response({"error": "product_id là bắt buộc."}, status=status.HTTP_400_BAD_REQUEST)
        if quantity < 1:
            return Response({"error": "quantity phải >= 1."}, status=status.HTTP_400_BAD_REQUEST)

        # Cross-service: Validate sản phẩm với Product Service
        product_data = _validate_product(product_id)
        if product_data is None:
            return Response(
                {"error": "Sản phẩm không hợp lệ hoặc Product Service không khả dụng."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        if product_data.get('stock', 0) < quantity:
            return Response(
                {"error": f"Không đủ hàng. Tồn kho hiện tại: {product_data['stock']}"},
                status=status.HTTP_409_CONFLICT
            )

        cart, _ = Cart.objects.get_or_create(customer_id=customer_id)
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product_id=product_id,
            defaults={
                'quantity':   quantity,
                'unit_price': product_data.get('price', 0)
            }
        )

        if not created:
            item.quantity  += quantity
            item.unit_price = product_data.get('price', item.unit_price)
            item.save()

        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    def put(self, request, customer_id, product_id=None):
        if product_id is None:
            return Response({"error": "product_id là bắt buộc."}, status=status.HTTP_400_BAD_REQUEST)

        quantity = int(request.data.get('quantity', 1))
        if quantity < 1:
            return Response({"error": "quantity phải >= 1."}, status=status.HTTP_400_BAD_REQUEST)

        # Cross-service: Validate sản phẩm với Product Service
        product_data = _validate_product(product_id)
        if product_data is None:
            return Response(
                {"error": "Sản phẩm không hợp lệ hoặc Product Service không khả dụng."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        if product_data.get('stock', 0) < quantity:
            return Response(
                {"error": f"Không đủ hàng. Tồn kho hiện tại: {product_data['stock']}"},
                status=status.HTTP_409_CONFLICT
            )

        try:
            cart = Cart.objects.get(customer_id=customer_id)
            item = CartItem.objects.get(cart=cart, product_id=product_id)
            item.quantity = quantity
            item.unit_price = product_data.get('price', item.unit_price)
            item.save()
            return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)
        except (Cart.DoesNotExist, CartItem.DoesNotExist):
            return Response({"error": "Sản phẩm không có trong giỏ hàng."}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, customer_id, product_id):
        try:
            cart = Cart.objects.get(customer_id=customer_id)
            CartItem.objects.filter(cart=cart, product_id=product_id).delete()
            return Response({"message": "Đã xóa sản phẩm khỏi giỏ."})
        except Cart.DoesNotExist:
            return Response({"error": "Giỏ hàng không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

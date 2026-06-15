import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import Category, Product
from .serializers import (
    ProductSerializer, ProductListSerializer,
    CategorySerializer, StockUpdateSerializer
)

logger = logging.getLogger(__name__)


class CategoryListView(APIView):
    """GET /api/products/categories/ — Danh sách 10 loại sản phẩm."""

    def get(self, request):
        categories = Category.objects.all()
        return Response(CategorySerializer(categories, many=True).data)


class ProductListCreateView(APIView):
    """
    GET  /api/products/        — Lấy danh sách sản phẩm (filter by category, search by name).
    POST /api/products/        — Tạo sản phẩm mới (Admin/Staff only).
    """

    def get(self, request):
        queryset = Product.objects.select_related('category').filter(is_active=True)

        # Filters
        category = request.query_params.get('category')
        search   = request.query_params.get('search')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')

        if category:
            queryset = queryset.filter(category__slug=category)
        if search:
            queryset = queryset.filter(name__icontains=search)
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        queryset = queryset.order_by('-created_at')

        # Pagination
        page_size = int(request.query_params.get('page_size', 20))
        page      = int(request.query_params.get('page', 1))
        start     = (page - 1) * page_size
        end       = start + page_size
        total     = queryset.count()

        serializer = ProductListSerializer(queryset[start:end], many=True)
        return Response({
            "count":    total,
            "page":     page,
            "page_size": page_size,
            "results":  serializer.data
        })

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductDetailView(APIView):
    """
    GET    /api/products/<pk>/ — Chi tiết sản phẩm.
    PUT    /api/products/<pk>/ — Cập nhật sản phẩm.
    DELETE /api/products/<pk>/ — Xóa mềm (is_active=False).
    """

    def get(self, request, pk):
        product    = get_object_or_404(Product, pk=pk, is_active=True)
        serializer = ProductSerializer(product)
        return Response(serializer.data)

    def put(self, request, pk):
        product    = get_object_or_404(Product, pk=pk)
        serializer = ProductSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        product.is_active = False
        product.save(update_fields=['is_active'])
        return Response({"message": "Sản phẩm đã được xóa."}, status=status.HTTP_200_OK)


class StockUpdateView(APIView):
    """
    PUT /api/products/<pk>/stock/
    Cập nhật tồn kho với Optimistic Locking để tránh race condition.
    Được gọi bởi Order Service / Cart Service.
    """

    def put(self, request, pk):
        product    = get_object_or_404(Product, pk=pk)
        serializer = StockUpdateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        delta            = serializer.validated_data['delta']
        expected_version = serializer.validated_data['expected_version']

        # Kiểm tra tồn kho đủ khi giảm
        if delta < 0 and product.stock + delta < 0:
            return Response(
                {"error": f"Không đủ tồn kho. Hiện còn {product.stock} sản phẩm."},
                status=status.HTTP_409_CONFLICT
            )

        success = product.update_stock(delta, expected_version)

        if success:
            product.refresh_from_db()
            logger.info(f"Stock updated: product_id={pk}, delta={delta}, new_stock={product.stock}")
            return Response({
                "message":     "Cập nhật tồn kho thành công.",
                "product_id":  pk,
                "new_stock":   product.stock,
                "new_version": product.version,
            })
        else:
            return Response(
                {"error": "Version conflict — vui lòng thử lại."},
                status=status.HTTP_409_CONFLICT
            )

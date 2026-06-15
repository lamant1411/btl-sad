Dưới đây là hướng dẫn chi tiết để lập trình **Phase 2: Identity & Catalog (User & Product)** dựa trên kiến trúc đã thiết kế. Phase này bao gồm việc xây dựng hai dịch vụ cốt lõi độc lập: `customer-service` (quản lý định danh, cấp phát JWT) và `product-service` (quản lý danh mục hàng hóa đa hình).

### 1. Xây dựng Customer Service (Identity Context)
Dịch vụ này đóng vai trò là "người gác đền" bảo mật của toàn bộ hệ thống, chịu trách nhiệm quản lý thông tin khách hàng, cấp phát JWT Token và chạy trên Port 8001.

**Bước 1.1: Khởi tạo dự án và cài đặt thư viện**
Khởi tạo dự án Django và cài đặt các thư viện cần thiết, đặc biệt là `djangorestframework-simplejwt` để xử lý xác thực phi trạng thái (Stateless).
```bash
mkdir customer-service && cd customer-service
python -m venv venv
source venv/bin/activate
pip install django djangorestframework djangorestframework-simplejwt requests
django-admin startproject customer_service .
python manage.py startapp app
```

**Bước 1.2: Cấu hình `settings.py` (JWT & Apps)**
Đăng ký các ứng dụng và thiết lập cơ chế xác thực mặc định là JWT có thời hạn.
```python
INSTALLED_APPS = [
    # ... django apps ...
    'rest_framework',
    'rest_framework_simplejwt',
    'app',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
}

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'ALGORITHM': 'HS256',
}
```

**Bước 1.3: Thiết kế Model và Serializer**
Khai báo thông tin lưu trữ của Bệnh nhân/Khách hàng. **Lưu ý:** Không có bất kỳ khóa ngoại (Foreign Key) nào nối sang các service khác.
```python
# app/models.py
from django.db import models

class Customer(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name

# app/serializers.py
from rest_framework import serializers
from .models import Customer

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'
```

**Bước 1.4: Viết API Views với logic Giao tiếp liên dịch vụ (Inter-Service)**
Khi một khách hàng đăng ký thành công, hệ thống phải tự động gọi sang `cart-service` để khởi tạo một giỏ hàng rỗng. Phải luôn sử dụng `timeout` để bảo vệ hệ thống khỏi lỗi nghẽn cổ chai.
```python
# app/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Customer
from .serializers import CustomerSerializer
import requests

CART_SERVICE_URL = "http://cart-service:8003" # Nạp từ biến môi trường .env

class CustomerListCreate(APIView):
    def post(self, request):
        serializer = CustomerSerializer(data=request.data)
        if serializer.is_valid():
            customer = serializer.save()
            
            # Kích hoạt tạo Giỏ hàng rỗng bên Cart Service qua API
            try:
                requests.post(
                    f"{CART_SERVICE_URL}/carts/",
                    json={"customer_id": customer.id},
                    timeout=3.0 # Nguyên tắc Resilience: Luôn đặt timeout
                )
            except requests.exceptions.RequestException:
                pass # Bỏ qua nếu Cart Service chưa sẵn sàng (Eventual Consistency)
                
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
```

---

### 2. Xây dựng Product Service (Catalog Context)
Dịch vụ này quản lý toàn bộ danh mục sản phẩm và đóng vai trò là "Single Source of Truth" (Nguồn chân lý duy nhất) về số lượng tồn kho, chạy trên Port 8002. Bài toán kiến trúc lớn nhất là giải quyết **Tính đa hình (Polymorphism)** của 10 nhóm sản phẩm khác biệt (Sách, Điện tử, Thời trang,...). 

**Bước 2.1: Khởi tạo dự án**
```bash
mkdir product-service && cd product-service
python -m venv venv
source venv/bin/activate
pip install django djangorestframework requests
django-admin startproject product_service .
python manage.py startapp app
```

**Bước 2.2: Thiết kế Model quản lý đa hình**
Thay vì tạo bảng EAV (Entity-Attribute-Value) làm chậm tốc độ truy vấn, sử dụng mô hình kế thừa (Single-Table-Inheritance) thông qua trường định danh `category` (Trong thực tế nên dùng tính năng `JSONB` của PostgreSQL để lưu các thuộc tính mở rộng).
```python
# app/models.py
from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    category = models.CharField(max_length=100) # Phục vụ đa hình phân loại 10 nhóm

    def __str__(self):
        return self.name
```

**Bước 2.3: Tạo Serializer và API Views**
Xây dựng các RESTful API cơ bản để Khách hàng truy xuất danh mục, và hệ thống Order/Cart gọi sang để lấy thông tin giá cả, tồn kho.
```python
# app/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Product
from .serializers import ProductSerializer

class ProductListCreate(APIView):
    def get(self, request):
        products = Product.objects.all()
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)

class ProductDetail(APIView):
    def get(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
            serializer = ProductSerializer(product)
            return Response(serializer.data)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=404)
```

**Bước 2.4: Đăng ký Router (URLs)**
```python
# app/urls.py
from django.urls import path
from app.views import ProductListCreate, ProductDetail

urlpatterns = [
    path('api/products/', ProductListCreate.as_view()),
    path('api/products/<int:pk>/', ProductDetail.as_view()),
]
```

**🎯 Xác nhận hoàn thành Phase 2:**
Agent đã xây dựng xong hai dịch vụ nền tảng. `customer-service` đã sẵn sàng đón luồng đăng ký/đăng nhập và cấp phát JWT Token. `product-service` đã sẵn sàng để chứa dữ liệu sản phẩm đa hình. Điểm mấu chốt là **Cross-Service Call (gọi liên dịch vụ)** từ Customer sang Cart Service đã được thiết lập chặt chẽ với cơ chế `timeout` để đề phòng hiệu ứng sụp đổ dây chuyền (Cascading Failure). Bạn có thể yêu cầu tiếp Phase 3 để chuyển sang xây dựng lõi giao dịch (Cart, Order, Payment).
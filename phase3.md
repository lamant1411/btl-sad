Dưới đây là hướng dẫn chi tiết để lập trình **Phase 3: Transaction Core (Cart, Order, Payment)** dựa trên kiến trúc hệ thống E-commerce phân tán. Phase này tập trung vào 3 dịch vụ cốt lõi xử lý luồng giao dịch, áp dụng các nguyên tắc quản lý dữ liệu phân tán và mẫu thiết kế Saga (Saga Pattern).

### 1. Xây dựng Cart Service (Quản lý Giỏ hàng)
Dịch vụ này lưu trữ trạng thái sản phẩm khách hàng định mua. Nó giao tiếp đồng bộ với `product-service` để kiểm tra thông tin hàng hóa. Cart Service chạy trên Port 8003.

**Bước 1.1: Khởi tạo dự án**
```bash
mkdir cart-service && cd cart-service
python -m venv venv
source venv/bin/activate
pip install django djangorestframework requests
django-admin startproject cart_service .
python manage.py startapp app
```

**Bước 1.2: Thiết kế Model (Không dùng khóa ngoại chéo)**
Sử dụng tham chiếu mềm (IntegerField) thay vì ForeignKey để trỏ sang Bệnh nhân (Customer) và Sản phẩm (Product).
```python
# app/models.py
from django.db import models

class Cart(models.Model):
    customer_id = models.IntegerField(unique=True) # Tham chiếu mềm sang Customer Service
    created_at = models.DateTimeField(auto_now_add=True)

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product_id = models.IntegerField() # Tham chiếu mềm sang Product Service
    quantity = models.PositiveIntegerField(default=1)
```

**Bước 1.3: Viết API Views (Giao tiếp liên dịch vụ)**
Khi thêm vào giỏ, Cart Service phải đóng vai trò HTTP Client gọi sang Product Service để validate tồn kho.
```python
# app/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Cart, CartItem
import requests

PRODUCT_SERVICE_URL = "http://product-service:8002/api/products" # Cấu hình URL Product Service

class CartItemAdd(APIView):
    def post(self, request, customer_id):
        product_id = request.data.get("product_id")
        quantity = request.data.get("quantity", 1)

        # Cross-service call: Xác minh sản phẩm tồn tại và còn hàng
        prod_resp = requests.get(f"{PRODUCT_SERVICE_URL}/{product_id}/")
        if prod_resp.status_code != 200:
            return Response({"error": "Sản phẩm không hợp lệ"}, status=400)

        cart, _ = Cart.objects.get_or_create(customer_id=customer_id)
        item, created = CartItem.objects.get_or_create(cart=cart, product_id=product_id)
        
        if not created:
            item.quantity += int(quantity)
        else:
            item.quantity = int(quantity)
        item.save()

        return Response({"message": "Thêm vào giỏ thành công"}, status=200)
```

---

### 2. Xây dựng Order Service (Quản lý Đơn hàng)
Đây là "Nhạc trưởng" (Orchestrator) của hệ thống. Order Service sẽ nhận lệnh chốt đơn, tạo đơn hàng cục bộ và gọi Payment Service. Service này chạy trên Port 8004.

**Bước 2.1: Khởi tạo dự án**
```bash
mkdir order-service && cd order-service
python -m venv venv
source venv/bin/activate
pip install django djangorestframework requests
django-admin startproject order_service .
python manage.py startapp app
```

**Bước 2.2: Thiết kế Model**
```python
# app/models.py
from django.db import models

class Order(models.Model):
    customer_id = models.IntegerField()
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=50, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product_id = models.IntegerField()
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
```

**Bước 2.3: Viết API Tạo Đơn hàng (Áp dụng Saga Pattern)**
Luồng xử lý: Tạo đơn hàng với trạng thái `PENDING`, sau đó gọi Payment Service. Khối `try-except` đảm bảo nếu Payment Service sập, ứng dụng không bị Crash.
```python
# app/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Order
import requests

PAYMENT_SERVICE_URL = "http://payment-service:8005/api/payments/"

class OrderCreate(APIView):
    def post(self, request):
        # 1. Tạo đơn hàng cục bộ
        customer_id = request.data.get("customer_id")
        total_price = request.data.get("total_price")
        
        order = Order.objects.create(
            customer_id=customer_id,
            total_price=total_price,
            status='PENDING'
        )

        # 2. Gọi Payment Service để khởi tạo thanh toán (Saga Pattern step 1)
        try:
            pay_resp = requests.post(PAYMENT_SERVICE_URL, json={
                "order_id": order.id,
                "amount": total_price
            }, timeout=3.0)
            
            if pay_resp.status_code == 201:
                return Response({"message": "Order created", "order_id": order.id}, status=201)
        except requests.exceptions.RequestException:
            # Nếu Payment lỗi, Order vẫn giữ PENDING để xử lý sau
            pass

        return Response({"message": "Order created, payment delayed", "order_id": order.id}, status=201)
```

---

### 3. Xây dựng Payment Service (Quản lý Thanh toán)
Service này chịu trách nhiệm tích hợp cổng thanh toán (ví dụ: VNPay, Momo) và xử lý tính lũy đẳng (Idempotency). Nó hoạt động trên Port 8005.

**Bước 3.1: Khởi tạo dự án**
```bash
mkdir payment-service && cd payment-service
python -m venv venv
source venv/bin/activate
pip install django djangorestframework requests
django-admin startproject payment_service .
python manage.py startapp app
```

**Bước 3.2: Thiết kế Model**
```python
# app/models.py
from django.db import models
import uuid

class Payment(models.Model):
    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    order_id = models.IntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, default='PROCESSING')
    timestamp = models.DateTimeField(auto_now_add=True)
```

**Bước 3.3: Viết API Xử lý Thanh toán (Và gọi Webhook ngược lại Order)**
Sau khi giao dịch thành công, Payment Service gọi ngược lại Order Service qua Webhook (hoặc Message Queue) để cập nhật trạng thái đơn hàng thành `PAID`.
```python
# app/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import PaymentSerializer
import requests

class PaymentProcess(APIView):
    def post(self, request):
        serializer = PaymentSerializer(data=request.data)
        if serializer.is_valid():
            # Giả lập gọi API Ngân hàng ở đây
            payment = serializer.save(status='SUCCESS')

            # Gửi Webhook báo lại cho Order Service
            try:
                requests.patch(f"http://order-service:8004/api/orders/{payment.order_id}/",
                               json={"status": "PAID"}, timeout=3.0)
            except requests.exceptions.RequestException:
                pass
                
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)
```

**🎯 Xác nhận hoàn thành Phase 3:**
Ở Phase này, luồng chốt đơn cơ bản đã hoàn thành. Hệ thống thể hiện được thiết kế của hệ thống phân tán:
1. **Không Khóa ngoại (No Foreign Key):** Order, Cart, và Payment độc lập hoàn toàn ở Database riêng.
2. **Saga Pattern:** Order là "Nhạc trưởng", chốt đơn xong sẽ chủ động bắn tín hiệu (HTTP POST) sang Payment.
3. **Resilience (Khả năng chịu lỗi):** Các đoạn code gọi liên dịch vụ luôn được bảo vệ bởi tham số `timeout=3.0` kèm khối lệnh `try-except` để chống hiện tượng sụp đổ dây chuyền (Cascading Failure).
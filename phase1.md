Dưới đây là hướng dẫn chi tiết để AI Agent (hoặc lập trình viên) tiến hành code **Phase 1: Infrastructure và API Gateway**, dựa trên bản thiết kế kiến trúc Microservices được cung cấp trong tài liệu.

Phase này tập trung vào việc thiết lập thư mục gốc, cấu hình môi trường Docker hóa (Containerization) và xây dựng API Gateway đóng vai trò là "người gác đền" (Single Entry Point) cho toàn bộ hệ thống,.

### Bước 1: Khởi tạo Cấu trúc Thư mục (Project Structure)
Đầu tiên, cần khởi tạo cấu trúc thư mục gốc cho dự án `ecom-final`. Hệ thống phân tách rõ ràng giữa Gateway, các Microservices và hạ tầng,.

Hãy tạo cây thư mục như sau:
```text
ecom-final/
├── gateway/                # Cấu hình Nginx & Dockerfile
│   └── nginx.conf
├── user-service/           # Xác thực & Phân quyền
├── product-service/        # Quản lý danh mục
├── cart-service/           # Logic giỏ hàng
├── order-service/          # Xử lý đơn hàng
├── payment-service/        # Xử lý thanh toán
├── shipping-service/       # Quản lý giao hàng
├── ai-service/             # FastAPI, mô hình LSTM & RAG
└── docker-compose.yml      # File điều phối Docker Compose
```

---

### Bước 2: Thiết lập Base Dockerfile cho các Microservices
Hệ thống sử dụng Docker để container hóa toàn bộ các dịch vụ nhằm đảm bảo sự đồng nhất. Đối với các service viết bằng Django (User, Product, Cart, Order, Payment, Shipping), hãy sử dụng cấu trúc `Dockerfile` chuẩn dưới đây và đặt vào từng thư mục service tương ứng,:

```dockerfile
# Dockerfile (dùng chung cho tất cả Django services)
FROM python:3.11-slim

# Thiết lập biến môi trường
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Cài đặt dependencies (tận dụng cache layer riêng)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers","2", "wsgi:application"]
```

---

### Bước 3: Cấu hình API Gateway (Nginx)
API Gateway được triển khai bằng NGINX dưới dạng reverse proxy, chịu trách nhiệm điều hướng (Routing), cân bằng tải (Load Balancing) và giới hạn tốc độ (Rate Limiting) để chống DDoS,.

Tạo file `gateway/nginx.conf` với nội dung cấu hình định tuyến đến các upstream services,,:

```nginx
# gateway/nginx.conf

upstream user_service    { server user-service:8000; }
upstream product_service { server product-service:8001; }
upstream cart_service    { server cart-service:8002; }
upstream order_service   { server order-service:8003; }
upstream payment_service { server payment-service:8004; }
upstream shipping_service{ server shipping-service:8005; }
upstream ai_service      { server ai-service:8006; }

server {
    listen 80;
    server_name localhost;

    # Rate limiting: Giới hạn 100 requests/giây trên toàn cục
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;

    location /api/users/ {
        limit_req zone=api burst=20;
        proxy_pass http://user_service;
        proxy_set_header Host            $host;
        proxy_set_header X-Real-IP       $remote_addr;
        proxy_set_header X-Service-Name  user-service;
    }

    location /api/products/ {
        proxy_pass http://product_service;
        proxy_set_header Host      $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ai/ {
        proxy_pass http://ai_service;
        proxy_read_timeout 60s;  # Tăng timeout do AI cần thêm thời gian xử lý
    }
    
    # Cấu hình tương tự cho các location khác (carts, orders, payments, shipping...)
}
```

---

### Bước 4: Điều phối hệ thống với Docker Compose
Để liên kết Gateway, các Microservices và hệ quản trị cơ sở dữ liệu (Database per Service), tạo file `docker-compose.yml` tại thư mục gốc,,,:

```yaml
version: '3.9'

services:
  # ── Databases (Polyglot Persistence) ──────────────────────────
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: postgres123
    volumes: [postgres_data:/var/lib/postgresql/data]

  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: mysql123
    volumes: [mysql_data:/var/lib/mysql]

  redis:
    image: redis:7-alpine

  # ── Microservices ───────────────────────────
  user-service:
    build: ./user-service
    ports: ["8000:8000"]
    depends_on: [mysql]
    environment:
      DATABASE_URL: mysql://root:mysql123@mysql/userdb
      SECRET_KEY: your-secret-key

  product-service:
    build: ./product-service
    ports: ["8001:8000"]
    depends_on: [postgres]
    environment:
      DATABASE_URL: postgres://postgres:postgres123@postgres/productd

  cart-service:
    build: ./cart-service
    ports: ["8002:8000"]
    depends_on: [postgres, redis]

  order-service:
    build: ./order-service
    ports: ["8003:8000"]
    depends_on: [postgres, redis]

  payment-service:
    build: ./payment-service
    ports: ["8004:8000"]
    depends_on: [mysql]

  shipping-service:
    build: ./shipping-service
    ports: ["8005:8000"]
    depends_on: [postgres]

  ai-service:
    build: ./ai-service
    ports: ["8006:8006"]
    depends_on: [redis]

  # ── API Gateway ────────────────────────────
  gateway:
    image: nginx:alpine
    ports: ["80:80"]
    volumes: 
      - ./gateway/nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - user-service
      - product-service
      - cart-service
      - order-service
      - payment-service
      - shipping-service
      - ai-service

volumes:
  postgres_data:
  mysql_data:
```

**🎯 Xác nhận hoàn thành Phase 1:**
Sau khi Agent hoàn thành các bước trên, hạ tầng mạng nội bộ của Docker đã kết nối thành công API Gateway với các Database độc lập (MySQL, PostgreSQL, Redis) và các thư mục Microservice. Bạn có thể sử dụng lệnh `docker-compose up -d` để khởi chạy nền tảng cơ sở này trước khi bắt tay vào code logic bên trong từng Service (Phase 2).
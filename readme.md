Dưới đây là bản phân tích và thiết kế hệ thống dưới định dạng `README.md`, được viết tối ưu hóa để đóng vai trò là "Blueprint" (Bản thiết kế) và "Prompt" (Lệnh hướng dẫn) cho một AI Agent có thể lập trình tự động dựa trên kiến trúc Microservices và AI.

***

# 📖 README: HỆ THỐNG E-COMMERCE TÍCH HỢP AI (MICROSERVICES)

## 1. TỔNG QUAN DỰ ÁN (PROJECT OVERVIEW)
Dự án xây dựng một hệ thống E-commerce hiện đại áp dụng triệt để kiến trúc **Microservices** kết hợp phương pháp luận **Domain-Driven Design (DDD)**. Hệ thống có khả năng chịu tải cao, cô lập lỗi tốt và tích hợp sâu AI (Deep Learning & RAG) để cá nhân hóa trải nghiệm người dùng.

---

## 2. KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)
Hệ thống tuân thủ 4 nguyên tắc vàng:
1. **Database per Service:** Tuyệt đối không dùng chung Database. Giao tiếp qua mạng. Không dùng Khóa ngoại (Foreign Key) xuyên DB, chỉ dùng tham chiếu mềm (Soft Link).
2. **API-First & Loose Coupling:** Giao tiếp đồng bộ qua REST API và bất đồng bộ qua Message Broker (Kafka/Redis PubSub).
3. **Stateless Authentication:** Sử dụng JWT cho toàn bộ quá trình xác thực.
4. **Containerization:** Đóng gói toàn bộ bằng Docker & Docker Compose.

### Stack Công nghệ
*   **API Gateway:** Nginx (Routing, Load Balancing, Rate Limiting).
*   **Backend Services:** Python (Django + Django REST Framework).
*   **AI Service:** Python (FastAPI, PyTorch, LangChain, FAISS).
*   **Databases (Polyglot Persistence):** PostgreSQL, MySQL, Redis.
*   **Message Broker:** Redis PubSub / Apache Kafka.

---

## 3. CẤU TRÚC THƯ MỤC (PROJECT STRUCTURE)
Agent cần khởi tạo dự án theo cấu trúc sau:
```text
ecom-final/
├── gateway/                # Nginx config & Dockerfile (Port 80)
├── common/                 # Tiện ích dùng chung (Auth, Logging)
├── user-service/           # Django - MySQL (Port 8000)
├── product-service/        # Django - PostgreSQL (Port 8001)
├── cart-service/           # Django - Redis/PostgreSQL (Port 8002)
├── order-service/          # Django - PostgreSQL (Port 8003)
├── payment-service/        # Django - MySQL/PostgreSQL (Port 8004)
├── shipping-service/       # Django - PostgreSQL (Port 8005)
├── ai-service/             # FastAPI - Redis/FAISS (Port 8006)
├── docker-compose.yml      # Orchestration
└── .env                    # Biến môi trường
```

---

## 4. ĐẶC TẢ CÁC MICROSERVICES (SERVICE SPECIFICATIONS)

### 4.1. User Service (Identity Context)
*   **Trách nhiệm:** Quản lý vòng đời tài khoản (RBAC: Customer, Staff, Admin) và cấp phát JWT Token.
*   **Database:** MySQL.
*   **Models:** `Role` (id, name, description), `User` (id, username, password, full_name, role_id).
*   **Core APIs:**
    *   `POST /api/users/auth/login`: Xác thực, trả về `access_token` và `refresh_token`.
    *   `POST /api/users/auth/register`: Đăng ký và gọi ngầm `POST /carts/` sang Cart Service để tạo giỏ hàng rỗng.

### 4.2. Product Service (Catalog Context)
*   **Trách nhiệm:** Quản lý danh mục, tính đa hình của 10 loại sản phẩm (Sách, Điện thoại, Thời trang...) và tồn kho (Inventory).
*   **Database:** PostgreSQL (Sử dụng tính năng JSONB cho các thuộc tính đa hình).
*   **Models:** `Category`, `Product` (Abstract Base Class), và 10 Subclasses kế thừa (Book, Electronics...).
*   **Core APIs:**
    *   `GET /api/products/`: Lấy danh sách sản phẩm.
    *   `PUT /api/products/{id}/stock`: Cập nhật tồn kho (Dùng Optimistic Locking).

### 4.3. Cart Service (Shopping Session Context)
*   **Trách nhiệm:** Quản lý phiên mua sắm tạm thời. Áp dụng TTL (Time to Live) tự động dọn rác.
*   **Database:** Redis (Tối ưu truy xuất <1ms).
*   **Models:** `Cart` (Aggregate Root), `CartItem` (Tham chiếu mềm `product_id`).
*   **Core APIs:**
    *   `POST /api/carts/`: Khởi tạo giỏ hàng.
    *   `POST /api/carts/{user_id}/items/`: Thêm item (Cần gọi đồng bộ sang Product Service để check tồn kho).

### 4.4. Order Service (Ordering Context - Core Domain)
*   **Trách nhiệm:** Nhạc trưởng (Orchestrator) của Saga Pattern. Xử lý logic chốt đơn.
*   **Database:** PostgreSQL.
*   **Models:** `Order` (Aggregate Root), `OrderItem`.
*   **Core APIs:**
    *   `POST /api/orders/`: Nhận payload, tạo Order (PENDING), xóa Cart, gọi Payment Service và bắn Event `ORDER_CREATED`.

### 4.5. Payment Service & Shipping Service
*   **Payment Service:** Xử lý giao dịch, tích hợp cổng thanh toán (Webhook IPN), đảm bảo tính lũy đẳng (Idempotency).
*   **Shipping Service:** Tích hợp đơn vị vận chuyển bên thứ 3, track lịch sử giao hàng.
*   **Giao tiếp:** Cả hai chủ yếu lắng nghe Event qua PubSub/Kafka và cập nhật trạng thái ngược lại cho Order Service.

### 4.6. AI Service (Recommendation & RAG)
*   **Trách nhiệm:** Gợi ý sản phẩm cá nhân hóa và AI Chatbot tư vấn.
*   **Mô hình DL:** Sử dụng mô hình **Deep Interest Network (DIN)** hoặc **LSTM** để nắm bắt chuỗi hành vi mua sắm.
*   **RAG Chatbot:** Nhúng danh mục sản phẩm vào Vector DB (FAISS), tìm kiếm độ tương đồng Cosine, trộn kết quả với DL Insight và gửi vào Prompt cho LLM.
*   **Core APIs (FastAPI):**
    *   `GET /api/v1/recommend/{user_id}`: Trả về Top K sản phẩm gợi ý (Đọc từ Redis Cache để đạt độ trễ <100ms).
    *   `POST /api/v1/chat`: Tích hợp RAG.

---

## 5. HƯỚNG DẪN DÀNH CHO AI AGENT (AGENT IMPLEMENTATION PROMPT)

**System Prompt for Agent:**
"Bạn là một Senior Backend/MLOps Engineer. Nhiệm vụ của bạn là lập trình hệ thống E-commerce Microservices theo đúng thiết kế trên. Hãy thực hiện code theo từng Phase một cách độc lập và tuần tự. Luôn tuân thủ nguyên tắc Không dùng Foreign Key giữa các DB."

### Lộ trình thực thi (Coding Phases):

#### Phase 1: Infrastructure & API Gateway
1. Tạo file `docker-compose.yml` chứa các containers: `postgres`, `mysql`, `redis`, `gateway`, và các microservices.
2. Viết file `gateway/nginx.conf` với cấu hình Rate Limiting và định tuyến (proxy_pass) cho các prefix `/api/users/`, `/api/products/`, `/api/ai/`, v.v..

#### Phase 2: Identity & Catalog (User & Product)
1. Khởi tạo Django project cho **User Service**. Thiết lập cấu hình SimpleJWT. Viết `Customer` model và APIs Login/Register.
2. Khởi tạo Django project cho **Product Service**. Viết cấu trúc Database hỗ trợ Đa hình (Polymorphism) cho 10 danh mục. Viết API lấy thông tin sản phẩm.

#### Phase 3: Transaction Core (Cart, Order, Payment)
1. Thiết lập **Cart Service** sử dụng Redis. Code API thêm sản phẩm vào giỏ, nhớ viết function gọi HTTP GET sang Product Service để validate tồn kho (cài đặt `timeout=3.0` để chống lỗi Cascading Failure).
2. Khởi tạo **Order Service**. Đây là cốt lõi. Viết luồng `create_order`:
   - Tạo DB nội bộ.
   - Dùng thư viện `redis` publish event `ORDER_CREATED`.
3. Code **Payment Service** có cơ chế listen PubSub `order.events`.

#### Phase 4: AI & Recommendation Engine
1. Khởi tạo **AI Service** bằng FastAPI.
2. Code một module giả lập mô hình LSTM/DIN (PyTorch) load từ file `.pth`.
3. Viết API `/recommend/{user_id}` thực hiện suy luận (Inference) và trả về JSON nhanh nhất có thể.
4. Cài đặt mô đun RAG cơ bản dùng LangChain kết nối với FAISS giả lập.

**Lưu ý quan trọng cho Agent:**
*   Sử dụng biến môi trường (ENV) để kết nối Database và gọi các dịch vụ khác (Ví dụ: `PRODUCT_SERVICE_URL=http://product-service:8001`).
*   Triển khai `try-except` cho tất cả các HTTP Request gọi liên dịch vụ, bắt lỗi Timeout và trả về HTTP 503 thay vì Crash App.
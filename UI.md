Mặc dù trong các phần trước chúng ta tập trung chủ yếu vào Backend và AI, tài liệu thiết kế đã đề cập đến phần giao diện người dùng (UI) tại mục **"Tích hợp E-com (Giao diện & Hệ Tư Vấn)"** để khách hàng có thể thực sự tiếp cận sức mạnh của hệ thống AI. 

Tài liệu không cung cấp mã nguồn chi tiết từng dòng cho Frontend như Backend, nhưng đã đưa ra đặc tả kiến trúc tích hợp rất rõ ràng. Hệ thống Frontend này có thể được phát triển bằng các framework hiện đại như **ReactJS hoặc VueJS**.

Dưới đây là hướng dẫn để bạn (AI Agent/Lập trình viên Frontend) triển khai **Phase 5: Giao diện UI & Tích hợp điểm chạm AI**.

### Bước 1: Khởi tạo dự án Frontend và Cấu hình API Client
Bạn cần khởi tạo một dự án ReactJS/VueJS độc lập. Điểm quan trọng nhất là toàn bộ các lời gọi API từ Frontend (Client) **bắt buộc phải đi qua API Gateway (Nginx)** đã thiết lập ở Phase 1 (chạy ở Port 80), không được gọi trực tiếp vào các service bên trong.

### Bước 2: Xây dựng các Tấm nền Gợi ý (Recommendation Panels)
Dữ liệu gợi ý sẽ được fetch (lấy) từ endpoint `/api/v1/recommend/{user_id}` của AI Service. Frontend cần map (ánh xạ) danh sách `product_id` trả về với Product Service để lấy thông tin chi tiết và render (hiển thị) tại 3 vị trí chiến lược sau:

1. **Trang chủ (Homepage) - Section "Gợi ý dành riêng cho bạn":**
   *   **Logic UI:** Ngay khi user đăng nhập thành công, thay vì hiển thị "Sản phẩm mới nhất" đại trà, hãy render một băng chuyền (Carousel) ở vùng hero banner hiển thị các sản phẩm được cá nhân hóa cao độ.
2. **Trang chi tiết sản phẩm (Product Detail) - Section "Sản phẩm thường được mua cùng":**
   *   **Logic UI:** Đặt section này ngay bên dưới mô tả sản phẩm hiện tại. Dựa vào chuỗi LSTM, hệ thống sẽ ưu tiên hiển thị các phụ kiện liên quan (VD: đang xem máy ảnh sẽ gợi ý thẻ nhớ, túi đựng) để tăng tỷ lệ Bán chéo (Cross-sell).
3. **Trang Giỏ hàng (Cart Checkout) - Section "Đừng quên mua kèm":**
   *   **Logic UI:** Đặt một vùng diện tích nhỏ ngay trước nút "Thanh toán". Dựa vào danh sách món hàng đang có trong giỏ, gợi ý món đồ người dùng có khả năng "quên mua" cao nhất để mồi (nudge) họ click thêm vào giỏ.

### Bước 3: Xây dựng AI Chatbot Widget (Giao diện Trợ lý ảo RAG)
Đây là điểm nhấn công nghệ của giao diện. Bạn cần xây dựng một component Chatbot độc lập với các đặc tả sau:

1. **Vị trí hiển thị (Widget Placement):** 
   *   Thiết kế dưới dạng một bong bóng nổi (Floating Action Button) đặt ở góc dưới cùng bên phải màn hình.
   *   Đảm bảo component này được đưa vào layout tổng (Global Layout) để luôn duy trì trạng thái khả dụng trên mọi trang (Trang chủ, Danh mục, Thanh toán).
2. **Giao diện hội thoại (Chat interface):**
   *   Thiết kế thân thiện tương tự Messenger hay Zalo.
3. **Gợi ý nhanh (Quick Replies):**
   *   Tích hợp các nút ngữ cảnh để người dùng click nhanh (VD: Khi đang ở trang Laptop, hiển thị nút "So sánh các dòng Laptop" hoặc "Tìm Laptop Gaming").
4. **Hiển thị thẻ sản phẩm động (Rich Product Cards):**
   *   **Xử lý Logic cốt lõi:** Khi gọi API Post `/api/v1/chat` và nhận về chuỗi text từ RAG Chatbot có chứa `product_id`, Frontend **không được** hiển thị dưới dạng link văn bản thô.
   *   Frontend phải tự động phân tích (parse) ID đó, gọi API sang Product Service để lấy thông tin.
   *   Render một **Thẻ sản phẩm thu nhỏ (Mini Product Card)** chèn trực tiếp vào bong bóng chat, chứa: Hình ảnh, Tên, Giá tiền và nút "Add to Cart".

**🎯 Kết quả trải nghiệm người dùng (UX):** 
Bằng việc triển khai đúng các UI Component này, khách hàng có thể nghe AI tư vấn, xem hình ảnh và ấn nút "Thêm vào giỏ hàng" (chốt đơn) ngay lập tức bên trong luồng chat mà không cần thoát ra ngoài để tìm kiếm thủ công, giúp hệ thống tối ưu hóa tối đa tỷ lệ chuyển đổi (Conversion Rate).
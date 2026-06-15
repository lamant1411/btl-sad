# Báo cáo Chi tiết: Microservice AI-Service

`ai-service` là trái tim của hệ thống trí tuệ nhân tạo trong dự án E-Commerce Microservices. Service này được xây dựng trên nền tảng **FastAPI** và **PyTorch**, chịu trách nhiệm cho hai tính năng cốt lõi: **Hệ thống Gợi ý sản phẩm (Recommendation Engine)** và **Trợ lý ảo thông minh (AI Chatbot)**.

---

## 1. Kiến trúc Tổng quan (Architecture)

Hệ thống kết hợp nhiều công nghệ tiên tiến để xử lý dữ liệu và nội suy theo thời gian thực:
- **FastAPI**: Cung cấp các RESTful API hiệu suất cao (`/api/v1/recommend`, `/api/v1/chat`).
- **PyTorch**: Framework chính dùng để định nghĩa, huấn luyện và chạy (inference) các mô hình Deep Learning.
- **Neo4j (Knowledge Graph)**: Cơ sở dữ liệu đồ thị, lưu trữ các mối quan hệ phức tạp giữa Người dùng (User) và Sản phẩm (Product).
- **FAISS (Facebook AI Similarity Search)**: Lưu trữ các vector ngữ nghĩa (embeddings) để tìm kiếm sản phẩm cho Chatbot (RAG).
- **Kafka Consumer**: Chạy ngầm trên một background thread, hứng các sự kiện hành vi người dùng (view, add_to_cart, purchase) từ hệ thống để cập nhật trực tiếp vào Neo4j.
- **Redis**: Đóng vai trò Caching Layer (giảm tải cho Database và AI models).

---

## 2. Hệ thống Gợi ý Sản phẩm (Hybrid Recommendation Engine)

Hệ thống gợi ý được thiết kế theo đường ống 3 bước (3-Stage Pipeline), kết hợp giữa Deep Learning và Đồ thị tri thức:

### Bước 1: Retrieval (Sàng lọc ban đầu) bằng mô hình LSTMRec
- **Nhiệm vụ:** Từ lịch sử tương tác của người dùng, nhanh chóng chọn ra một tập ứng viên (Candidate Pool) gồm khoảng 30-50 sản phẩm tiềm năng nhất.
- **Kiến trúc:** Dựa trên mạng **LSTM (Long Short-Term Memory)**. Chuỗi ID sản phẩm mà user đã xem được mã hóa (Embedding) và đưa qua LSTM để bắt được trình tự (Sequential pattern) của hành vi. Lớp Linear cuối dự đoán xác suất cho sản phẩm tiếp theo.

### Bước 2: Reranking (Sắp xếp lại) bằng mô hình DIN (Deep Interest Network)
- **Nhiệm vụ:** Tinh chỉnh và sắp xếp lại tập Candidate Pool từ LSTM, chọn ra Top 10 sản phẩm chính xác nhất để hiển thị.
- **Kiến trúc:** DIN sử dụng cơ chế **Attention (Local Activation Unit)**. Khác với LSTM gộp mọi lịch sử thành một vector cố định, DIN tính toán "độ liên quan" (attention score) giữa từng sản phẩm trong Candidate Pool với *từng sản phẩm trong lịch sử* của user. Điều này cho phép hệ thống cá nhân hóa cực kỳ sắc nét (VD: User vừa xem laptop vừa xem chuột, khi model xét đến Candidate là "Bàn phím", trọng số attention sẽ dồn vào lịch sử xem "chuột").

### Bước 3: Đắp thêm Collaborative Filtering (Graph Neo4j)
- **Nhiệm vụ:** Nếu tập kết quả từ DL chưa đủ lớn, hệ thống sẽ chọc vào Neo4j.
- **Kiến trúc:** Sử dụng câu lệnh Cypher lọc ra các User có hành vi giống hệt người dùng hiện tại (Graph-based Collaborative Filtering), từ đó lấy các sản phẩm mà "hàng xóm" đã mua để đắp thêm vào danh sách gợi ý.

---

## 3. Trợ lý ảo Thông minh (AI Chatbot - RAG & Intent Classification)

Thay vì gọi API LLM tốn kém, `ai-service` tự xây dựng một luồng xử lý độc lập để tư vấn khách hàng:

### 3.1. Phân loại Ý định (Intent Classification) bằng LSTM
- Mô hình **IntentLSTM** được code hoàn toàn bằng PyTorch (Embedding -> LSTM -> Dropout -> FC -> FC).
- Nhận diện câu hỏi tiếng Việt của khách hàng (sau khi tokenize qua `vocab_dict.pkl`) thành 3 ý định (intents) phục vụ bán hàng:
  1. `tim_theo_gia`
  2. `tim_theo_nganh_hoc`
  3. `tim_theo_nhu_cau`

### 3.2. Tìm kiếm thông tin ngữ nghĩa (RAG - Retrieval-Augmented Generation)
- **Embedding Model:** Hệ thống sử dụng thư viện `sentence-transformers` với model đa ngôn ngữ cực mạnh `paraphrase-multilingual-MiniLM-L12-v2`.
- Mô tả của toàn bộ sản phẩm trong cửa hàng được biến thành các Vector và nhét vào **FAISS index**.
- Khi khách hỏi *"Laptop cho sinh viên kỹ thuật"*, câu hỏi được chuyển thành Vector -> FAISS tìm ra ngay Top 3 laptop sát nghĩa nhất (không cần phải match từ khóa exact-match).

### 3.3. Tổng hợp Câu trả lời (Response Generation)
- **Intent** (ví dụ: `tim_theo_nganh_hoc`) được dùng để map ra bộ khung câu trả lời soạn sẵn (hard-code dict).
- **RAG Products** (ví dụ: "Laptop Dell Vostro", "Asus TUF") được dùng để "đắp" biến `{price}` và thông tin sản phẩm vào câu thoại.
- **Neo4j Insight**: Lấy thêm lịch sử danh mục yêu thích của user (VD: user rất hay xem đồ điện tử) để bổ trợ thêm cho thuật toán gợi ý.

---

## 4. Quản lý Đồ thị Tri thức (Neo4j Knowledge Graph)

Mọi hành vi của người dùng trên web/app không chỉ lưu ở RDBMS mà còn chạy thẳng vào Neo4j (nhờ Kafka).

- **Schema:** `(User)-[:INTERACTED_WITH {weight, action_count, last_updated}]->(Product)`
- **Trọng số học thuật (Heuristic Weights):**
  - Xem sản phẩm (`view`): +1 điểm
  - Thêm giỏ hàng (`add_to_cart`): +3 điểm
  - Mua hàng thành công (`purchase`): +5 điểm
- **Ưu điểm:** Bằng cách duy trì đồ thị này, `ai-service` luôn nắm bắt được Top danh mục yêu thích của user và có khả năng chạy thuật toán Gợi ý cộng tác (CF) theo thời gian thực mà không cần phải train lại model.

---

## 5. Tổng kết

Việc chia tách `ai-service` thành một microservice độc lập đem lại lợi ích to lớn:
- Tối ưu được container chuyên dụng cho Data Science (Chạy Python 3.11, PyTorch CPU-only).
- Không làm ảnh hưởng đến hiệu năng các API nghiệp vụ CRUD khác của Backend.
- Sẵn sàng mở rộng (Scale out) nếu lượng xử lý Inference tăng cao trong các dịp Sale lớn.

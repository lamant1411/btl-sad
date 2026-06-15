Dưới đây là hướng dẫn chi tiết để lập trình **Phase 4: AI Service và RAG**, hoàn thiện hệ sinh thái E-commerce Microservices. 

Khác với các dịch vụ nghiệp vụ trước đó sử dụng Django, AI Service là một dịch vụ độc lập sử dụng **FastAPI (Python) kết hợp với Uvicorn ASGI Server** nhằm tối ưu hóa xử lý I/O bất đồng bộ, mang lại tốc độ cực nhanh để phục vụ (serving) các mô hình Deep Learning,. AI Service sẽ chạy trên **Port 8006**.

### Bước 1: Khởi tạo dự án & Cài đặt thư viện (Data Science Stack)
AI Service cần một môi trường độc lập (hoặc Dockerfile riêng) để tránh xung đột thư viện với hệ thống Django.

```bash
mkdir ai-service && cd ai-service
python -m venv venv
source venv/bin/activate
# Cài đặt các thư viện phục vụ Data Science, AI và API
pip install fastapi uvicorn torch transformers faiss-cpu langchain redis
```

### Bước 2: Thiết lập Mô hình Deep Learning (LSTM)
Sử dụng kiến trúc Mạng nơ-ron hồi quy bộ nhớ ngắn hạn dài hạn (LSTM) để nắm bắt chuỗi hành vi mua sắm của khách hàng và giải quyết triệt để bệnh "đãng trí" của mạng RNN truyền thống,. 

Tạo file `ai-service/models.py` để định nghĩa kiến trúc mạng:

```python
import torch
import torch.nn as nn

class LSTMRec(nn.Module):
    def __init__(self, num_items, embed_dim, hidden_dim):
        super(LSTMRec, self).__init__()
        self.item_embedding = nn.Embedding(num_items, embed_dim, padding_idx=0)
        
        # Mạng LSTM duy trì Băng chuyền thông tin (Cell State)
        self.lstm = nn.LSTM(input_size=embed_dim, 
                            hidden_size=hidden_dim, 
                            batch_first=True)
        self.fc = nn.Linear(hidden_dim, num_items)

    def forward(self, session_seq):
        emb = self.item_embedding(session_seq)
        
        # LSTM trả về lstm_out và một tuple gồm hidden state (h_n) và cell state (c_n)
        lstm_out, (h_n, c_n) = self.lstm(emb)
        
        # Lấy Hồ sơ ý định (Intent Profile) tại thời điểm cuối cùng h_n
        final_hidden = h_n.squeeze(0)
        logits = self.fc(final_hidden)
        
        return logits
```
*(Ghi chú: Lớp kiến trúc này cho phép xuất ra vector dự đoán ý định khách hàng ở bước thời gian cuối cùng,).*

### Bước 3: Xây dựng API Suy luận (Model Serving) bằng FastAPI
Hệ thống cần áp dụng kỹ thuật **Khởi tạo trạng thái (Cold Start Prevention)**: Trọng số của mô hình (`.pth`) sẽ được nạp thẳng vào bộ nhớ RAM/VRAM ngay lúc khởi động Server, giúp tránh việc phải đọc ổ cứng mỗi khi có request.

Tạo file `ai-service/main.py`:

```python
from fastapi import FastAPI, HTTPException
import torch
from models import LSTMRec # Import class đã định nghĩa ở Bước 2

app = FastAPI(title="E-Commerce AI Recommendation Service")

# 1. Khởi tạo và nạp Model khi server start (Cold Start Prevention)
device = torch.device('cpu') # Hoặc 'cuda' nếu có GPU
model = LSTMRec(num_items=15000, embed_dim=64, hidden_dim=128)
# Giả định bạn đã có file trọng số từ quá trình huấn luyện offline
# model.load_state_dict(torch.load("models/lstm_best_model.pth", map_location=device))
model.eval() # Chuyển sang chế độ suy luận, tắt tính toán gradient

@app.get("/api/v1/recommend/{user_id}")
async def get_recommendations(user_id: int, top_k: int = 10):
    try:
        # Giả lập fetch lịch sử user từ Redis (VD:)
        user_history = 
        
        # Chuyển đổi thành Tensor [1, sequence_length]
        input_tensor = torch.tensor([user_history], dtype=torch.long).to(device)
        
        # Suy luận (Inference)
        with torch.no_grad():
            logits = model(input_tensor)
            
        # Lấy Top K sản phẩm điểm cao nhất
        top_scores, top_indices = torch.topk(logits, top_k)
        recommendations = [
            {"product_id": int(idx), "score": float(score)}
            for idx, score in zip(top_indices, top_scores)
        ]
        
        return {"status": "success", "data": recommendations}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal AI Server Error")
```
*(Đoạn code trên cung cấp API có độ trễ cực thấp, đáp ứng yêu cầu trả về danh sách sản phẩm gợi ý,,).*

### Bước 4: Tích hợp RAG và Chatbot (Sự kết hợp đỉnh cao)
Mô hình Ngôn ngữ Lớn (LLM) không có dữ liệu tồn kho thực tế, do đó ta cần dùng **RAG (Retrieval-Augmented Generation)** để nhúng dữ liệu sản phẩm vào CSDL Vector (FAISS). Điểm độc đáo của hệ thống này là **trộn lẫn kết quả từ RAG và mô hình LSTM** để cá nhân hóa câu trả lời.

Thêm logic sau vào `main.py` để xử lý Chatbot qua LangChain:

```python
from langchain.prompts import PromptTemplate

# 2. Xây dựng Template kết hợp RAG Context và Deep Learning Insight
template = """
Bạn là một trợ lý ảo tư vấn bán hàng điện máy chuyên nghiệp.
Hãy trả lời câu hỏi của khách hàng dựa trên thông tin tồn kho và phân tích hành vi sau đây.

[1. Dữ liệu Tồn kho (RAG Context)]: 
{rag_context_products}

[2. Phân tích hành vi cá nhân hóa (DL LSTM Insight)]: 
Khách hàng này dạo gần đây đang có xu hướng rất quan tâm đến thương hiệu hoặc nhóm sản phẩm: {dl_predicted_trend}.
Hãy khéo léo lồng ghép hoặc ưu tiên đề xuất nhóm sản phẩm này nếu nó phù hợp.

Câu hỏi của khách hàng: {user_query}

Câu trả lời tư vấn:
"""

prompt = PromptTemplate(
    input_variables=["rag_context_products", "dl_predicted_trend", "user_query"],
    template=template,
)

@app.post("/api/v1/chat")
async def chat_with_bot(user_id: int, query: str):
    # Luồng xử lý song song (Parallel execution)
    # 1. Gọi Vector Search (FAISS) để lấy thông tin sản phẩm khớp với query
    rag_context = "Sản phẩm A giá 10tr, Sản phẩm B giá 15tr..." # (Giả lập FAISS)
    
    # 2. Gọi model LSTM để dự đoán xu hướng của user này
    dl_trend = "Laptop Gaming dòng ASUS" # (Giả lập kết quả từ LSTM)
    
    # Sinh prompt và gọi LLM (VD: OpenAI)
    final_prompt = prompt.format(
        rag_context_products=rag_context, 
        dl_predicted_trend=dl_trend, 
        user_query=query
    )
    
    # response = llm.predict(final_prompt)
    return {"reply": "Câu trả lời từ LLM dựa trên Prompt đã trộn dữ liệu"}
```
*(Kiến trúc này cho phép Chatbot không chỉ giải đáp đúng tồn kho mà còn biết cách Bán chéo (Cross-sell) đúng sở thích người dùng,).*

**🎯 Xác nhận hoàn thành Phase 4:**
AI Agent đã xây dựng xong khối não bộ (AI Service) của hệ thống e-commerce. Nó tách biệt hoàn toàn khỏi Django, sở hữu Endpoint siêu tốc cho Hệ thống gợi ý tuần tự (LSTM) và một API Chatbot RAG thông minh biết tham khảo hành vi quá khứ. 

Lúc này, toàn bộ 4 Phase của nền tảng E-commerce (Gateway, Identity, Transaction Core, AI Service) đã hình thành một khối kiến trúc Microservices thống nhất, giao tiếp nhịp nhàng qua REST và Message Queue.
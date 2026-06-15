Để xây dựng **AI Service** cho hệ thống E-commerce, chúng ta sẽ không sử dụng Django như các dịch vụ khác mà thiết kế nó dưới dạng một dịch vụ độc lập chạy trên **FastAPI (Python) kết hợp với Uvicorn ASGI Server**. Việc này giúp tận dụng hệ sinh thái học máy và khả năng xử lý I/O bất đồng bộ (Asynchronous I/O) cho tốc độ cực nhanh.

Dưới đây là hướng dẫn chi tiết từng bước và mã nguồn để xây dựng AI Service:

### Bước 1: Thiết lập dự án và Cấu trúc thư mục
Khởi tạo cấu trúc thư mục riêng biệt cho AI Service để tránh xung đột môi trường.
```text
ai-service/
├── main.py                 # File chạy chính của FastAPI
├── models/                 # Chứa trọng số (.pth) và class kiến trúc (LSTM, DIN)
├── core/                   # Logic ETL xử lý dữ liệu và cấu hình RAG
└── Dockerfile              # Đóng gói độc lập
```
Các thư viện cốt lõi cần cài đặt bao gồm: `fastapi`, `uvicorn`, `torch` (PyTorch), `transformers`, `faiss-cpu`, và `langchain`.

### Bước 2: Viết mã Tiền xử lý dữ liệu (ETL Pipeline)
Để AI có thể hiểu được chuỗi hành vi mua sắm (như xem lướt, thêm vào giỏ, mua hàng), dữ liệu thô phải được chuyển đổi thành các chuỗi tuần tự (Sequences) thông qua kỹ thuật **Cửa sổ trượt (Sliding Window)**. 

Tạo file `core/etl.py`:
```python
import pandas as pd

def generate_sliding_windows(df, seq_length=10):
    """
    Sắp xếp, gom nhóm dữ liệu theo User và áp dụng thuật toán Sliding Window
    để tạo các chuỗi tuần tự làm đầu vào cho mô hình Deep Learning.
    """
    # 1. Sắp xếp theo User và Thời gian
    df = df.sort_values(by=['user_idx', 'timestamp'])
    
    # 2. Gom nhóm hành vi theo từng User
    user_sequences = df.groupby('user_idx').apply(
        lambda x: list(zip(x['product_idx'], x['action_id'], x['timestamp']))
    ).reset_index(name='history')
    
    # 3. Kỹ thuật Cửa sổ trượt
    final_dataset = []
    for _, row in user_sequences.iterrows():
        user = row['user_idx']
        hist = row['history']
        
        # Chỉ lấy các user có đủ dữ liệu tạo thành ít nhất 1 chuỗi
        if len(hist) > 2:
            for i in range(1, len(hist)):
                start_idx = max(0, i - seq_length)
                seq = hist[start_idx:i] # Trích xuất Lịch sử quá khứ
                target = hist[i]        # Nhãn dự đoán (Sản phẩm tiếp theo)
                final_dataset.append({
                    'user_idx': user,
                    'sequence': seq,
                    'target_item': target
                })
    return pd.DataFrame(final_dataset)
```

### Bước 3: Viết mã Mô hình Học sâu (LSTM)
Mạng **Long Short-Term Memory (LSTM)** được sử dụng để giải quyết bài toán triệt tiêu đạo hàm của RNN, giúp hệ thống ghi nhớ được ý định mua hàng dài hạn thông qua **Băng chuyền thông tin (Cell State)**. 

Tạo file `models/lstm.py`:
```python
import torch
import torch.nn as nn

class LSTMRec(nn.Module):
    def __init__(self, num_items, embed_dim, hidden_dim):
        super(LSTMRec, self).__init__()
        self.item_embedding = nn.Embedding(num_items, embed_dim, padding_idx=0)
        
        # Mạng LSTM thay thế cho RNN
        self.lstm = nn.LSTM(input_size=embed_dim, 
                            hidden_size=hidden_dim, 
                            batch_first=True)
        self.fc = nn.Linear(hidden_dim, num_items)

    def forward(self, session_seq):
        emb = self.item_embedding(session_seq)
        
        # LSTM trả về lstm_out và tuple gồm hidden state (h_n) và cell state (c_n)
        lstm_out, (h_n, c_n) = self.lstm(emb)
        
        # Lấy Hồ sơ ý định (Intent Profile) tại thời điểm cuối cùng h_n
        final_hidden = h_n.squeeze(0)
        logits = self.fc(final_hidden)
        
        return logits
```

### Bước 4: Viết API Phục vụ Suy luận (FastAPI)
Để đảm bảo **độ trễ suy luận cực thấp (<100ms)**, hệ thống áp dụng kỹ thuật chống "Cold Start" bằng cách nạp toàn bộ trọng số mạng nơ-ron vào RAM/VRAM ngay lúc khởi động máy chủ.

Tạo file `main.py`:
```python
from fastapi import FastAPI, HTTPException
import torch
from models.lstm import LSTMRec

app = FastAPI(title="E-Commerce AI Recommendation Service")

# 1. Khởi tạo và nạp Model khi server start
device = torch.device('cpu') # Hoặc 'cuda' nếu có GPU
model = LSTMRec(num_items=10000, embed_dim=64, hidden_dim=128) # Khởi tạo kiến trúc
# Nạp file trọng số từ quá trình huấn luyện offline
model.load_state_dict(torch.load("models/lstm_best_model.pth", map_location=device))
model.eval() # Chuyển model sang chế độ suy luận, tắt tính toán gradient

# API Gợi ý sản phẩm
@app.get("/api/v1/recommend/{user_id}")
async def get_recommendations(user_id: int, top_k: int = 10):
    try:
        # Lấy lịch sử user_id (Thường từ Redis Cache để đạt tốc độ cao)
        user_history = # Giả lập dữ liệu trả về
        
        # Chuyển đổi thành Tensor
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

### Bước 5: Viết mã tích hợp AI Chatbot (RAG + Deep Learning)
Đây là sự kết hợp đỉnh cao của hệ thống: **Trộn lẫn kết quả từ hệ thống truy xuất (RAG qua FAISS) và hệ thống dự đoán chuỗi (LSTM)** để cung cấp câu trả lời tư vấn hoàn toàn cá nhân hóa cho từng khách hàng.

Bổ sung đoạn mã sau vào `main.py` sử dụng LangChain:
```python
from langchain.prompts import PromptTemplate

# Xây dựng Template kết hợp RAG Context và Deep Learning Insight
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
    # 1. Gọi Vector Database (như FAISS) để lấy thông tin sản phẩm khớp với query
    rag_context = "..." # Thực thi vector search tại đây
    
    # 2. Gọi model LSTM để dự đoán xu hướng mua sắm tiếp theo
    dl_trend = "..." # Gọi hàm dự đoán từ LSTM
    
    # Trộn dữ liệu vào Prompt
    final_prompt = prompt.format(
        rag_context_products=rag_context, 
        dl_predicted_trend=dl_trend, 
        user_query=query
    )
    
    # Gửi final_prompt đến LLM (như OpenAI GPT) và trả về kết quả
    return {"reply": "Câu trả lời từ LLM"}
```

Sau khi hoàn thành các đoạn mã này, toàn bộ AI Service có thể được đóng gói bằng Docker và liên kết vào hệ thống qua NGINX Gateway, đảm bảo tính rời rạc và cô lập lỗi đối với hệ thống nghiệp vụ (Django).
Để xây dựng module **Knowledge Graph (Đồ thị tri thức) với Neo4j, kết hợp RAG (FAISS) và API Chatbot** cho AI Service, chúng ta sẽ dựa trên kiến trúc đã được thiết kế bằng FastAPI. Theo đặc tả, hệ thống AI sẽ sử dụng FAISS để tìm kiếm theo ngữ nghĩa (RAG) và dùng Neo4j để lưu trữ, cập nhật trọng số các sự kiện tương tác của người dùng.

Dưới đây là hướng dẫn chi tiết và mã nguồn để AI Agent triển khai tính năng này:

### Bước 1: Cài đặt thư viện bổ sung
Vào thư mục `ai-service/`, cài đặt các thư viện kết nối cơ sở dữ liệu đồ thị, vector và xử lý ngôn ngữ tự nhiên:
```bash
pip install neo4j langchain faiss-cpu sentence-transformers openai kafka-python
```

### Bước 2: Khởi tạo module kết nối Neo4j (Knowledge Graph)
Hệ thống sử dụng Message Broker (Kafka) để nhận các luồng sự kiện (view, add_to_cart...) và AI Service sẽ tiêu thụ (consume) các sự kiện này để cập nhật trọng số (event weights) trên đồ thị tri thức Neo4j.

Tạo file `ai-service/core/graph_db.py`:
```python
from neo4j import GraphDatabase

class Neo4jKnowledgeGraph:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def update_interaction_weight(self, user_id, product_id, action_type):
        """
        Cập nhật trọng số sự kiện trong đồ thị tri thức dựa trên hành vi người dùng.
        """
        # Quy đổi action thành điểm số (giống Logic mã hóa hành vi)
        weight_map = {'view': 1, 'add_to_cart': 3, 'purchase': 5}
        weight = weight_map.get(action_type, 1)

        query = """
        MERGE (u:User {id: $user_id})
        MERGE (p:Product {id: $product_id})
        MERGE (u)-[r:INTERACTED_WITH]->(p)
        ON CREATE SET r.weight = $weight, r.last_updated = timestamp()
        ON MATCH SET r.weight = r.weight + $weight, r.last_updated = timestamp()
        """
        with self.driver.session() as session:
            session.run(query, user_id=user_id, product_id=product_id, weight=weight)

    def get_user_favorite_categories(self, user_id, limit=2):
        """
        Truy vấn đồ thị để lấy các danh mục sản phẩm user tương tác nhiều nhất.
        """
        query = """
        MATCH (u:User {id: $user_id})-[r:INTERACTED_WITH]->(p:Product)-[:BELONGS_TO]->(c:Category)
        RETURN c.name AS category, SUM(r.weight) AS total_weight
        ORDER BY total_weight DESC LIMIT $limit
        """
        with self.driver.session() as session:
            result = session.run(query, user_id=user_id, limit=limit)
            return [record["category"] for record in result]
```

### Bước 3: Xây dựng module RAG với FAISS
Toàn bộ dữ liệu sản phẩm (tên, cấu hình, giá) từ PostgreSQL sẽ được nhúng (embedding) và lưu vào FAISS để thực hiện tìm kiếm độ tương đồng Cosine, giúp cung cấp thông tin tồn kho thực tế cho LLM.

Tạo file `ai-service/core/rag_engine.py`:
```python
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings

class ProductRAG:
    def __init__(self, openai_api_key):
        self.embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
        # Trong thực tế, bạn sẽ load index đã lưu: FAISS.load_local("faiss_index", self.embeddings)
        # Ở đây giả lập khởi tạo index rỗng
        self.vector_store = None 

    def build_index(self, product_texts):
        """Hàm này dùng để đồng bộ dữ liệu từ Product Service sang FAISS"""
        self.vector_store = FAISS.from_texts(product_texts, self.embeddings)

    def retrieve_context(self, query: str, k: int = 3):
        """Tìm kiếm Top K sản phẩm sát nghĩa nhất với câu hỏi"""
        if not self.vector_store:
            return "Dữ liệu sản phẩm đang được cập nhật."
        
        docs = self.vector_store.similarity_search(query, k=k)
        # Nối các kết quả thành một chuỗi văn bản để đưa vào Prompt
        context = "\n".join([f"- {doc.page_content}" for doc in docs])
        return context
```

### Bước 4: Tích hợp API Chatbot (Sự kết hợp giữa RAG, DL và Graph)
Đây là cốt lõi của hệ thống tư vấn. Khi user chat, hệ thống chạy song song: Gọi FAISS để lấy tồn kho (RAG), và gọi LSTM/Neo4j để lấy Insight sở thích, sau đó trộn vào Prompt Template.

Cập nhật file `ai-service/main.py`:
```python
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatOpenAI
import asyncio

from core.graph_db import Neo4jKnowledgeGraph
from core.rag_engine import ProductRAG
# Giả định đã import mô hình LSTM từ models.py như các phần trước

app = FastAPI(title="E-Commerce AI Service")

# Khởi tạo các kết nối
neo4j_graph = Neo4jKnowledgeGraph(uri="bolt://neo4j:7687", user="neo4j", password="password123")
rag_engine = ProductRAG(openai_api_key="YOUR_OPENAI_KEY")
llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0.7)

# Template chuẩn theo thiết kế kiến trúc
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

class ChatRequest(BaseModel):
    user_id: str
    query: str

@app.post("/api/v1/chat")
async def chat_with_bot(request: ChatRequest):
    # 1. Luồng xử lý song song (Parallel execution)
    
    # Task A: Lấy thông tin sản phẩm bằng RAG (FAISS)
    loop = asyncio.get_event_loop()
    rag_context = await loop.run_in_executor(None, rag_engine.retrieve_context, request.query)
    
    # Task B: Lấy Insight sở thích từ Đồ thị Neo4j (và/hoặc LSTM)
    fav_categories = await loop.run_in_executor(None, neo4j_graph.get_user_favorite_categories, request.user_id)
    dl_trend = ", ".join(fav_categories) if fav_categories else "Chưa có dữ liệu rõ ràng"
    
    # 2. Trộn dữ liệu vào Prompt
    final_prompt = prompt.format(
        rag_context_products=rag_context, 
        dl_predicted_trend=dl_trend, 
        user_query=request.query
    )
    
    # 3. Gọi LLM sinh câu trả lời
    response = await loop.run_in_executor(None, llm.predict, final_prompt)
    
    # Giao diện Frontend sẽ tự động parse các product_id trong response thành Mini Product Card
    return {"reply": response}
```

### Bước 5: Viết Background Task tiêu thụ Kafka Event
Để đồ thị Neo4j luôn được cập nhật theo thời gian thực (real-time) mà không làm chậm hệ thống, AI Service cần một worker chạy ngầm để lắng nghe Kafka.

Thêm vào `ai-service/main.py`:
```python
import json
from kafka import KafkaConsumer
import threading

def consume_kafka_events():
    """Worker chạy ngầm lắng nghe các sự kiện để cập nhật Neo4j"""
    consumer = KafkaConsumer(
        'user_behavior_events',
        bootstrap_servers=['message-broker:9092'],
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    for message in consumer:
        data = message.value
        user_id = data.get('user_id')
        product_id = data.get('product_id')
        action = data.get('action') # 'view', 'add_to_cart', 'purchase'
        
        # Cập nhật trọng số trên Knowledge Graph
        if user_id and product_id and action:
            neo4j_graph.update_interaction_weight(user_id, product_id, action)

@app.on_event("startup")
async def startup_event():
    # Kích hoạt Kafka Consumer chạy trên một thread riêng biệt
    thread = threading.Thread(target=consume_kafka_events, daemon=True)
    thread.start()
```

**Lưu ý quan trọng cho Agent:**
*   **Bảo vệ hệ thống:** Việc tách riêng AI Service (vốn tiêu tốn nhiều tài nguyên) chạy trên FastAPI giúp thông lượng của các dịch vụ nghiệp vụ cốt lõi (như Đặt hàng, Thanh toán) không bị sụt giảm khi AI đang tính toán mô hình phức tạp. 
*   **Anti-Hallucination:** Nhờ có FAISS (RAG Context), Chatbot sẽ chỉ tư vấn những sản phẩm thực sự tồn tại trong kho thay vì bịaa đặt thông tin.
*   **Neo4j & Kafka:** Trong tệp `docker-compose.yml`, hãy đảm bảo đã khai báo image `neo4j:latest` và `confluentinc/cp-kafka` để dịch vụ AI này có thể kết nối được.
"""
AI Service — FastAPI Main Application
Tích hợp: LSTM Recommendation + FAISS RAG + Neo4j Knowledge Graph + Kafka Consumer
"""
import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import List, Optional

import httpx
import redis as redis_client
import torch
from decouple import config
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models.lstm import LSTMRec
from models.din import DINModel
from core.rag import RAGEngine
from core.graph_db import Neo4jKnowledgeGraph
from models.intent_lstm import IntentChatbotWrapper
from core.nlp_utils import load_pickle, text_to_sequence

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────
REDIS_URL           = config("REDIS_URL",           default="redis://redis:6379/0")
PRODUCT_SERVICE_URL = config("PRODUCT_SERVICE_URL",  default="http://product-service:8000")
OPENAI_API_KEY      = config("OPENAI_API_KEY",       default="")
LLM_PROVIDER        = config("LLM_PROVIDER",         default="openai")
NUM_ITEMS           = config("NUM_ITEMS",             default=11,    cast=int)
EMBED_DIM           = config("EMBED_DIM",             default=64,    cast=int)
HIDDEN_DIM          = config("HIDDEN_DIM",            default=128,   cast=int)
TOP_K               = config("TOP_K",                 default=10,    cast=int)

# DIN model config (fixed to match din.pth weights)
DIN_NUM_ITEMS       = 515   # from din.pth item_embedding shape
DIN_EMBED_DIM       = 64
DIN_MODEL_PATH      = "model_weights/din.pth"

# Neo4j config
NEO4J_URI           = config("NEO4J_URI",      default="bolt://neo4j:7687")
NEO4J_USER          = config("NEO4J_USER",     default="neo4j")
NEO4J_PASSWORD      = config("NEO4J_PASSWORD", default="password123")

# Kafka config
KAFKA_BOOTSTRAP     = config("KAFKA_BOOTSTRAP_SERVERS", default="kafka:9092")
KAFKA_TOPIC         = config("KAFKA_TOPIC", default="user_behavior_events")

MODEL_PATH          = "model_weights/lstm_best_model.pth"
HISTORY_CACHE_KEY   = "user_history:{user_id}"
RECOMMEND_CACHE_KEY = "recommend:{user_id}:k{top_k}"
CACHE_TTL           = 3600   # 1 hour

# ── Global State ────────────────────────────────────────────
_model:       LSTMRec              = None
_din_model:   DINModel             = None
_rag_engine:  RAGEngine            = None
_neo4j_graph: Neo4jKnowledgeGraph  = None
_device:      torch.device         = None
_redis_conn                        = None
_chatbot_model: IntentChatbotWrapper = None
_vocab_dict                        = None
_label_encoder                     = None

# Hard-coded responses
BOT_RESPONSES = {
    "tim_theo_gia": "Dạ, hệ thống đã lọc ra các sản phẩm theo yêu cầu. Ví dụ sản phẩm tốt nhất hiện có giá là {price}. Mời bạn xem các gợi ý bên dưới:",
    "tim_theo_nganh_hoc": "Dạ, đối với ngành học của bạn, laptop cần cấu hình chuyên dụng. Mình xin đề xuất các mẫu máy phù hợp nhất bên dưới nhé:",
    "tim_theo_nhu_cau": "Dạ, để đáp ứng tốt nhu cầu sử dụng của bạn, cửa hàng xin gợi ý các sản phẩm nổi bật sau đây:",
    "fallback": "Xin lỗi, mình chưa hiểu rõ ý bạn. Bạn có thể nói rõ hơn hoặc tham khảo các sản phẩm bên dưới nhé."
}


# ── Kafka Consumer Thread ───────────────────────────────────
def _start_kafka_consumer():
    """
    Worker chạy ngầm trên thread riêng, lắng nghe Kafka topic 'user_behavior_events'.
    Mỗi event nhận được → cập nhật trọng số trên Knowledge Graph Neo4j.
    """
    try:
        from kafka import KafkaConsumer
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=[KAFKA_BOOTSTRAP],
            auto_offset_reset="latest",
            group_id="ai-service-graph-updater",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            consumer_timeout_ms=1000,  # non-blocking poll
        )
        logger.info(f"[Kafka] Consumer started on topic '{KAFKA_TOPIC}' ✓")
        while True:
            try:
                for message in consumer:
                    data       = message.value
                    user_id    = data.get("user_id")
                    product_id = data.get("product_id")
                    action     = data.get("action")   # 'view', 'add_to_cart', 'purchase'
                    if user_id and product_id and action and _neo4j_graph:
                        _neo4j_graph.update_interaction_weight(user_id, product_id, action)
            except Exception as inner:
                logger.warning(f"[Kafka] Poll error: {inner}. Retrying in 5s...")
                time.sleep(5)
    except ImportError:
        logger.warning("[Kafka] kafka-python not installed. Consumer skipped.")
    except Exception as e:
        logger.warning(f"[Kafka] Consumer failed to start: {e}. Graph will not receive real-time events.")


# ── Helper: Fetch products ──────────────────────────────────
async def _fetch_all_products() -> List[dict]:
    """Lấy toàn bộ sản phẩm từ Product Service để build FAISS index và đồng bộ Neo4j."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{PRODUCT_SERVICE_URL}/api/products/?page_size=1000")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", [])
    except Exception as e:
        logger.warning(f"[Startup] Failed to fetch products: {e}. Using empty catalog.")
    return []


# ── Startup / Shutdown ─────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cold-Start: nạp model, kết nối DB, build indexes, khởi động Kafka consumer."""
    global _model, _din_model, _rag_engine, _neo4j_graph, _device, _redis_conn, _chatbot_model, _vocab_dict, _label_encoder

    logger.info("=== AI Service Starting Up ===")
    _device = torch.device("cpu")

    # 1. Load LSTM model
    logger.info(f"[LSTM] Initializing LSTMRec(num_items={NUM_ITEMS}, embed={EMBED_DIM}, hidden={HIDDEN_DIM})")
    _model = LSTMRec(num_items=NUM_ITEMS, embed_dim=EMBED_DIM, hidden_dim=HIDDEN_DIM)
    if os.path.exists(MODEL_PATH):
        _model.load_state_dict(torch.load(MODEL_PATH, map_location=_device))
        logger.info(f"[LSTM] Weights loaded from {MODEL_PATH} ✓")
    else:
        logger.warning(f"[LSTM] No weights at '{MODEL_PATH}'. Using random weights (demo mode).")
    _model.to(_device)
    _model.eval()
    logger.info("[LSTM] Model ready ✓")

    # 1b. Load DIN model
    logger.info(f"[DIN] Initializing DINModel(num_items={DIN_NUM_ITEMS}, embed_dim={DIN_EMBED_DIM})")
    _din_model = DINModel(num_items=DIN_NUM_ITEMS, embed_dim=DIN_EMBED_DIM)
    if os.path.exists(DIN_MODEL_PATH):
        state = torch.load(DIN_MODEL_PATH, map_location=_device, weights_only=False)
        _din_model.load_state_dict(state, strict=True)
        logger.info(f"[DIN] Weights loaded from {DIN_MODEL_PATH} ✓")
    else:
        logger.warning(f"[DIN] No weights at '{DIN_MODEL_PATH}'. Using random weights.")
    _din_model.to(_device)
    _din_model.eval()
    logger.info("[DIN] Model ready ✓")

    # 1c. Load IntentLSTM Chatbot
    vocab_path = "model_weights/vocab_dict.pkl"
    label_path = "model_weights/label_encoder.pkl"
    
    _vocab_dict = load_pickle(vocab_path)
    _label_encoder = load_pickle(label_path)
    
    if _vocab_dict and _label_encoder:
        vocab_size = max(_vocab_dict.values()) + 2 if _vocab_dict else 10000
        num_classes = len(_label_encoder.classes_) if hasattr(_label_encoder, 'classes_') else len(_label_encoder)
        
        _chatbot_model = IntentChatbotWrapper(vocab_size=vocab_size, num_classes=num_classes, device=str(_device))
        # Sử dụng đúng tên file model mà người dùng đề cập
        _chatbot_model.load_weights("model_weights/Chatbot_LSTM.pth")
        logger.info("[IntentLSTM] Chatbot Model ready ✓")
    else:
        logger.warning("[IntentLSTM] Missing vocab_dict.pkl or label_encoder.pkl. Chatbot degraded.")

    # 2. Redis
    try:
        _redis_conn = redis_client.from_url(REDIS_URL, decode_responses=True)
        _redis_conn.ping()
        logger.info("[Redis] Connected ✓")
    except Exception as e:
        logger.warning(f"[Redis] Connection failed: {e}. Cache disabled.")
        _redis_conn = None

    # 3. Neo4j Knowledge Graph
    _neo4j_graph = Neo4jKnowledgeGraph(
        uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
    )

    # 4. Fetch products & Build FAISS + Sync Neo4j
    logger.info("[RAG] Fetching product catalog from Product Service...")
    products = await _fetch_all_products()

    logger.info("[RAG] Building FAISS index...")
    _rag_engine = RAGEngine()
    _rag_engine.build_index(products)
    logger.info(f"[RAG] FAISS index ready with {len(products)} products ✓")

    if _neo4j_graph.is_available:
        logger.info("[Neo4j] Syncing product nodes to Knowledge Graph...")
        _neo4j_graph.bulk_upsert_products(products)

    # 5. Start Kafka Consumer thread (daemon — tự tắt khi app shutdown)
    kafka_thread = threading.Thread(target=_start_kafka_consumer, daemon=True)
    kafka_thread.start()

    logger.info("=== AI Service Ready ===")
    yield

    # Cleanup
    logger.info("=== AI Service Shutting Down ===")
    if _neo4j_graph:
        _neo4j_graph.close()


app = FastAPI(
    title="E-Commerce AI Service",
    description="LSTM Recommendation + FAISS RAG + Neo4j Knowledge Graph",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic Models ──────────────────────────────────────────
class ChatRequest(BaseModel):
    user_id: int
    query:   str

class InteractionRequest(BaseModel):
    user_id:    int
    product_id: int
    action:     str   # 'view' | 'add_to_cart' | 'purchase' | 'remove'

class RecommendResponse(BaseModel):
    status:     str
    user_id:    int
    top_k:      int
    latency_ms: float
    data:       List[dict]

class ChatResponse(BaseModel):
    status:       str
    user_id:      int
    query:        str
    reply:        str
    rag_products: List[dict]
    graph_insight: dict


# ── Helper: User History ────────────────────────────────────
def _get_user_history(user_id: int, seq_length: int = 10) -> List[int]:
    """Lấy lịch sử hành vi user từ Redis cache."""
    if _redis_conn:
        cache_key = HISTORY_CACHE_KEY.format(user_id=user_id)
        try:
            history_str = _redis_conn.get(cache_key)
            if history_str:
                return json.loads(history_str)[-seq_length:]
        except Exception:
            pass
    return _mock_user_history(user_id, seq_length)


def _mock_user_history(user_id: int, seq_length: int = 10) -> List[int]:
    import random
    random.seed(user_id)
    return [random.randint(1, max(1, NUM_ITEMS - 1)) for _ in range(seq_length)]


def _get_user_trend_from_lstm(user_id: int) -> str:
    """Dự đoán xu hướng mua sắm của user từ LSTM output."""
    history = _get_user_history(user_id)
    if not history:
        return "Sản phẩm phổ biến"
    input_tensor = torch.tensor([history], dtype=torch.long).to(_device)
    with torch.no_grad():
        logits = _model(input_tensor)
        top_idx = torch.argmax(logits).item()
    categories = ["Laptop", "Điện thoại", "Thời trang", "Sách", "Gia dụng"]
    return categories[top_idx % len(categories)]


async def _call_llm(prompt: str) -> str:
    """Hàm này hiện không còn dùng nữa do đã thay bằng Intent Classifier."""
    return "Tính năng LLM đã bị tắt."


# ── API Endpoints ────────────────────────────────────────────

@app.get("/api/v1/recommend/{user_id}", response_model=RecommendResponse,
         summary="Gợi ý sản phẩm cá nhân hóa (LSTM → DIN rerank)")
async def get_recommendations(
    user_id: int,
    top_k: int = Query(default=TOP_K, ge=1, le=50)
):
    """
    Pipeline 3 bước:
      1. LSTM   — tạo candidate pool (top 2×top_k sản phẩm)
      2. DIN    — rerank candidates dựa trên attention với lịch sử chi tiết
      3. Neo4j  — bổ sung Collaborative Filtering nếu thiếu candidates
    """
    start_time = time.time()
    cache_key  = RECOMMEND_CACHE_KEY.format(user_id=user_id, top_k=top_k)

    # Kiểm tra Redis cache
    if _redis_conn:
        try:
            cached = _redis_conn.get(cache_key)
            if cached:
                return RecommendResponse(
                    status="success (cached)",
                    user_id=user_id,
                    top_k=top_k,
                    latency_ms=round((time.time() - start_time) * 1000, 2),
                    data=json.loads(cached)
                )
        except Exception:
            pass

    try:
        history = _get_user_history(user_id, seq_length=10)

        # ── Bước 1: LSTM tạo candidate pool ────────────────────
        input_tensor = torch.tensor([history], dtype=torch.long).to(_device)
        # Lấy pool rộng hơn để DIN có nhiều candidates để rerank
        pool_size = min(top_k * 3, NUM_ITEMS - 1)
        _, lstm_indices = _model.get_top_k(input_tensor, k=pool_size)
        candidate_ids = [int(i) for i in lstm_indices.tolist() if int(i) > 0]

        # ── Bước 2: DIN rerank candidates ──────────────────────
        if _din_model is not None and candidate_ids:
            # Clip history IDs để không vượt quá DIN vocabulary (515)
            din_history = [min(h, DIN_NUM_ITEMS - 1) for h in history]
            # Clip candidate IDs tương tự
            din_candidates = [c for c in candidate_ids if 0 < c < DIN_NUM_ITEMS]

            if din_candidates:
                hist_tensor = torch.tensor(din_history, dtype=torch.long).to(_device)
                din_ranked  = _din_model.rank_candidates(
                    history_ids=hist_tensor,
                    candidate_ids=din_candidates,
                    device=str(_device),
                    top_k=top_k,
                )
                recommendations = [
                    {
                        "product_id": r["product_id"],
                        "score":      round(r["score"], 4),
                        "model":      "din",
                    }
                    for r in din_ranked
                ]
            else:
                # fallback: dùng LSTM score trực tiếp
                lstm_scores, _ = _model.get_top_k(input_tensor, k=top_k)
                recommendations = [
                    {"product_id": int(i), "score": round(float(s), 4), "model": "lstm"}
                    for i, s in zip(lstm_indices.tolist(), lstm_scores.tolist())
                    if int(i) > 0
                ][:top_k]
        else:
            # DIN chưa sẵn sàng — dùng LSTM trực tiếp
            lstm_scores, lstm_idx = _model.get_top_k(input_tensor, k=top_k)
            recommendations = [
                {"product_id": int(i), "score": round(float(s), 4), "model": "lstm"}
                for i, s in zip(lstm_idx.tolist(), lstm_scores.tolist())
                if int(i) > 0
            ][:top_k]

        # ── Bước 3: Collaborative Filtering bổ sung (Neo4j) ────
        if _neo4j_graph and _neo4j_graph.is_available:
            existing_ids = {r["product_id"] for r in recommendations}
            cf_ids = _neo4j_graph.get_similar_users_products(user_id, limit=3)
            for pid in cf_ids:
                if pid not in existing_ids and len(recommendations) < top_k:
                    recommendations.append({"product_id": pid, "score": 0.0, "model": "collaborative"})

        recommendations = recommendations[:top_k]

        # Cache kết quả
        if _redis_conn and recommendations:
            try:
                _redis_conn.setex(cache_key, CACHE_TTL, json.dumps(recommendations))
            except Exception:
                pass

        return RecommendResponse(
            status="success",
            user_id=user_id,
            top_k=top_k,
            latency_ms=round((time.time() - start_time) * 1000, 2),
            data=recommendations
        )
    except Exception as e:
        logger.error(f"[Recommend] Error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="AI Inference Error")


@app.post("/api/v1/chat", response_model=ChatResponse,
          summary="RAG Chatbot tư vấn sản phẩm (RAG + Neo4j + LSTM)")
async def chat_with_bot(request: ChatRequest):
    """
    RAG Chatbot nâng cao: kết hợp 3 nguồn tri thức:
    1. FAISS (RAG) — Lấy sản phẩm sát nghĩa với câu hỏi.
    2. Neo4j (Graph) — Lấy danh mục yêu thích của user.
    3. LSTM (DL) — Dự đoán xu hướng mua sắm.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query không được trống.")

    # 1. RAG: sản phẩm liên quan từ FAISS
    rag_products = _rag_engine.search(request.query, top_k=3)

    # 2. Graph: insight hành vi từ Neo4j
    graph_insight = {}
    dl_trend      = _get_user_trend_from_lstm(request.user_id)

    if _neo4j_graph and _neo4j_graph.is_available:
        graph_insight = _neo4j_graph.get_user_interaction_summary(request.user_id)
        fav_categories = graph_insight.get("favorite_categories", [])
        if fav_categories:
            # Kết hợp insight Neo4j vào trend
            dl_trend = ", ".join(fav_categories)

    # 3. Predict Intent và chọn Response
    reply = BOT_RESPONSES["fallback"]
    intent_name = "unknown"
    
    if _chatbot_model and _vocab_dict and _label_encoder:
        try:
            seq = text_to_sequence(request.query, _vocab_dict, max_length=50)
            pred_idx = _chatbot_model.predict_intent(seq)
            
            # Ánh xạ ID ra Tên Intent
            if hasattr(_label_encoder, 'inverse_transform'):
                intent_name = _label_encoder.inverse_transform([pred_idx])[0]
            elif isinstance(_label_encoder, dict):
                # Nếu label_encoder lưu kiểu dict (idx -> name)
                intent_name = _label_encoder.get(pred_idx, "fallback")
            elif hasattr(_label_encoder, 'classes_'):
                # Handle case where inverse_transform isn't directly available but classes_ is
                intent_name = _label_encoder.classes_[pred_idx]
            else:
                intent_name = str(pred_idx)
                
            # Lấy câu trả lời tương ứng với intent, nếu không có thì trả về câu mặc định kèm tên intent
            reply = BOT_RESPONSES.get(intent_name, f"Trợ lý ảo nhận diện bạn đang muốn: [{intent_name}], nhưng chưa có câu trả lời soạn sẵn cho việc này.")
            
            # Nếu khách hỏi giá, đắp thông tin giá từ RAG vào
            if rag_products:
                p = rag_products[0] # Lấy sản phẩm sát nhất
                price_str = str(p.get('price', 'Liên hệ'))
                reply = reply.replace("{price}", price_str + "đ")
            else:
                reply = reply.replace("{price}", "Liên hệ")
                
        except Exception as e:
            logger.error(f"[Chatbot] Intent inference error: {e}")
            reply = "Xin lỗi, hệ thống phân tích ý định đang gặp sự cố."

    # 4. Ghi nhận sự kiện chat vào Knowledge Graph (async, non-blocking)
    if _neo4j_graph and _neo4j_graph.is_available:
        for p in rag_products:
            _neo4j_graph.update_interaction_weight(
                user_id=request.user_id,
                product_id=p.get("id", 0),
                action_type="view"
            )

    return ChatResponse(
        status="success",
        user_id=request.user_id,
        query=request.query,
        reply=reply,
        rag_products=rag_products,
        graph_insight=graph_insight,
    )


@app.post("/api/v1/interaction", summary="Ghi nhận hành vi người dùng vào Knowledge Graph")
async def record_interaction(req: InteractionRequest):
    """
    Nhận event trực tiếp từ Frontend/Services mà không cần qua Kafka.
    Dùng cho: view sản phẩm, add to cart, mua hàng.
    Các action hợp lệ: 'view', 'add_to_cart', 'purchase', 'remove'
    """
    valid_actions = set(Neo4jKnowledgeGraph.WEIGHT_MAP.keys())
    if req.action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Action không hợp lệ. Chọn: {list(valid_actions)}")

    if _neo4j_graph and _neo4j_graph.is_available:
        _neo4j_graph.update_interaction_weight(req.user_id, req.product_id, req.action)

    # Cập nhật lịch sử Redis
    if _redis_conn:
        cache_key = HISTORY_CACHE_KEY.format(user_id=req.user_id)
        try:
            history = json.loads(_redis_conn.get(cache_key) or "[]")
            history.append(req.product_id)
            history = history[-50:]   # giữ 50 hành vi gần nhất
            _redis_conn.setex(cache_key, CACHE_TTL * 24, json.dumps(history))
        except Exception:
            pass

    return {"status": "ok", "message": f"Recorded {req.action} on product {req.product_id}"}


@app.get("/api/v1/graph/user/{user_id}", summary="Insight đồ thị tri thức của user")
async def get_graph_insight(user_id: int):
    """Truy vấn Neo4j để lấy thống kê hành vi, danh mục yêu thích và gợi ý CF."""
    if not (_neo4j_graph and _neo4j_graph.is_available):
        raise HTTPException(status_code=503, detail="Knowledge Graph không khả dụng.")

    summary = _neo4j_graph.get_user_interaction_summary(user_id)
    return {"status": "ok", "user_id": user_id, "graph_data": summary}


@app.get("/api/v1/health", summary="Health check")
async def health_check():
    model_ready = _model is not None
    rag_ready   = _rag_engine is not None and _rag_engine._is_built
    neo4j_ready = _neo4j_graph is not None and _neo4j_graph.is_available
    redis_ready = False
    if _redis_conn:
        try:
            _redis_conn.ping()
            redis_ready = True
        except Exception:
            pass
    return {
        "status":      "ok" if model_ready else "degraded",
        "lstm_ready":  model_ready,
        "din_ready":   _din_model is not None,
        "rag_ready":   rag_ready,
        "neo4j_ready": neo4j_ready,
        "redis_ready": redis_ready,
        "num_items":   NUM_ITEMS,
        "din_num_items": DIN_NUM_ITEMS,
    }


@app.get("/api/v1/rebuild-index", summary="Rebuild FAISS index + Sync Neo4j")
async def rebuild_index():
    """Admin: Rebuild FAISS khi có sản phẩm mới, đồng bộ Neo4j."""
    products = await _fetch_all_products()
    _rag_engine.build_index(products)
    if _neo4j_graph and _neo4j_graph.is_available:
        _neo4j_graph.bulk_upsert_products(products)
    return {"message": f"Rebuilt FAISS + Neo4j with {len(products)} products."}

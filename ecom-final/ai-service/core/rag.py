"""
AI Service — RAG Module
FAISS Vector Search + LangChain Prompt Engineering
"""
import json
import logging
import os
from typing import List, Optional, Tuple

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from langchain.prompts import PromptTemplate

logger = logging.getLogger(__name__)


class RAGEngine:
    """
    Retrieval-Augmented Generation Engine.
    Nhúng mô tả sản phẩm vào FAISS và tìm kiếm theo cosine similarity.
    """

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        """
        Args:
            model_name: Sentence Transformer model để tạo embeddings.
                        'all-MiniLM-L6-v2' — nhỏ gọn (80MB), nhanh, đủ tốt cho demo.
        """
        logger.info(f"[RAG] Loading sentence transformer: {model_name}")
        self.encoder    = SentenceTransformer(model_name)
        self.embed_dim  = self.encoder.get_sentence_embedding_dimension()

        # FAISS index — dùng Inner Product (cosine similarity sau khi normalize)
        self.index      = faiss.IndexFlatIP(self.embed_dim)
        self.products   = []     # List of product dicts
        self.product_ids = []    # Mapping index → product_id
        self._is_built  = False

        # LangChain Prompt Template
        self._prompt = PromptTemplate(
            input_variables=["rag_context_products", "dl_predicted_trend", "user_query"],
            template="""Bạn là một trợ lý ảo tư vấn bán hàng điện máy chuyên nghiệp và thân thiện.
Hãy trả lời câu hỏi của khách hàng dựa trên thông tin tồn kho và phân tích hành vi sau đây.

[1. Dữ liệu Tồn kho (RAG Context)]:
{rag_context_products}

[2. Phân tích hành vi cá nhân hóa (DL LSTM Insight)]:
Khách hàng này dạo gần đây đang có xu hướng quan tâm đến: {dl_predicted_trend}.
Hãy khéo léo lồng ghép hoặc ưu tiên đề xuất nhóm sản phẩm này nếu phù hợp.

Câu hỏi của khách hàng: {user_query}

Câu trả lời tư vấn (trả lời bằng tiếng Việt, thân thiện, ngắn gọn dưới 200 từ):"""
        )

    def build_index(self, products: List[dict]):
        """
        Xây dựng FAISS index từ danh sách sản phẩm.
        Gọi lúc startup — không gọi mỗi request.
        """
        if not products:
            logger.warning("[RAG] No products provided for indexing.")
            return

        self.products    = products
        self.product_ids = [p['id'] for p in products]

        # Tạo text mô tả đa dạng cho mỗi SP
        texts = []
        for p in products:
            attrs = ' '.join(str(v) for v in p.get('attributes', {}).values())
            text  = f"{p['name']} {p.get('description', '')} {attrs} {p.get('category', '')}"
            texts.append(text)

        logger.info(f"[RAG] Encoding {len(texts)} product descriptions...")
        embeddings = self.encoder.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        embeddings = embeddings.astype(np.float32)

        self.index.reset()
        self.index.add(embeddings)
        self._is_built = True
        logger.info(f"[RAG] FAISS index built with {self.index.ntotal} vectors (dim={self.embed_dim})")

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        """
        Tìm kiếm sản phẩm liên quan đến query bằng cosine similarity.
        Returns list of product dicts.
        """
        if not self._is_built or self.index.ntotal == 0:
            logger.warning("[RAG] Index not built yet.")
            return []

        query_vec = self.encoder.encode([query], normalize_embeddings=True).astype(np.float32)
        scores, indices = self.index.search(query_vec, min(top_k, self.index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self.products):
                product = self.products[idx].copy()
                product['similarity_score'] = float(score)
                results.append(product)
        return results

    def build_rag_context(self, query: str, top_k: int = 3) -> str:
        """Trả về string mô tả sản phẩm liên quan để inject vào prompt."""
        products = self.search(query, top_k)
        if not products:
            return "Không tìm thấy sản phẩm liên quan trong hệ thống."

        lines = []
        for i, p in enumerate(products, 1):
            raw_price = p.get('price')
            try:
                price_val = float(raw_price) if raw_price else 0
                price_str = f"{price_val:,.0f}đ" if price_val > 0 else "Liên hệ"
            except (ValueError, TypeError):
                price_str = str(raw_price) if raw_price else "Liên hệ"
                
            stock     = p.get('stock', 0)
            stock_str = f"Còn {stock} sản phẩm" if stock > 0 else "Hết hàng"
            lines.append(
                f"{i}. **{p['name']}** — Giá: {price_str} — {stock_str}\n"
                f"   {p.get('description', '')}"
            )
        return "\n".join(lines)

    def format_prompt(self, user_query: str, dl_trend: str, top_k: int = 3) -> str:
        """Tạo prompt hoàn chỉnh từ RAG context + DL trend."""
        rag_context = self.build_rag_context(user_query, top_k)
        return self._prompt.format(
            rag_context_products=rag_context,
            dl_predicted_trend=dl_trend,
            user_query=user_query
        )
